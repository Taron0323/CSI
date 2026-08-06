from __future__ import annotations

import math

import torch
from torch import Tensor, nn
import torch.nn.functional as F


def complex_csi(csi: Tensor) -> Tensor:
    if csi.shape[-1] % 2:
        raise ValueError("CSI must store all real values followed by all imaginary values")
    half = csi.shape[-1] // 2
    return torch.complex(csi[..., :half], csi[..., half:])


def real_imag_csi(csi: Tensor) -> Tensor:
    return torch.cat((csi.real, csi.imag), dim=-1)


def relative_power_db(csi: Tensor, floor: float = 1e-12) -> Tensor:
    values = complex_csi(csi)
    return 10.0 * torch.log10(torch.mean(values.abs() ** 2, dim=-1).clamp_min(floor))


class MapCNN(nn.Module):
    def __init__(self, channels: int, hidden: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(channels, hidden, 3, padding=1),
            nn.GELU(),
            nn.Conv2d(hidden, hidden, 3, padding=1),
            nn.GELU(),
            nn.AdaptiveAvgPool2d(1),
        )

    def forward(self, maps: Tensor) -> Tensor:
        return self.network(maps).flatten(1)


class SigMapLocator(nn.Module):
    """Map-conditioned CSI fingerprint locator used for the SigMap control."""

    def __init__(self, csi_dim: int, map_channels: int, context_dim: int, hidden: int):
        super().__init__()
        self.csi = nn.Sequential(
            nn.Linear(csi_dim, 2 * hidden),
            nn.GELU(),
            nn.Linear(2 * hidden, hidden),
        )
        self.map = MapCNN(map_channels, hidden)
        self.context = nn.Sequential(nn.Linear(context_dim, hidden), nn.GELU())
        self.fusion = nn.Sequential(
            nn.Linear(3 * hidden, 2 * hidden),
            nn.GELU(),
            nn.Linear(2 * hidden, hidden),
            nn.GELU(),
            nn.Linear(hidden, 2),
        )

    def forward(self, csi: Tensor, maps: Tensor, context: Tensor) -> Tensor:
        return self.fusion(torch.cat((self.csi(csi), self.map(maps), self.context(context)), dim=1))

    def training_loss(self, csi: Tensor, maps: Tensor, context: Tensor, receiver_xy: Tensor) -> Tensor:
        return F.huber_loss(self(csi, maps, context), receiver_xy)


class SparseSceneEncoder(nn.Module):
    def __init__(self, map_channels: int, context_dim: int, dim: int, heads: int, layers: int, grid_size: int):
        super().__init__()
        if dim % heads:
            raise ValueError("WiSER scene dimension must be divisible by its head count")
        self.grid_size = int(grid_size)
        self.map_projection = nn.Linear(map_channels + 3, dim)
        self.tx_projection = nn.Sequential(nn.Linear(context_dim, dim), nn.GELU(), nn.Linear(dim, dim))
        layer = nn.TransformerEncoderLayer(
            dim, heads, 4 * dim, batch_first=True, norm_first=True, dropout=0.0, activation="gelu"
        )
        self.encoder = nn.TransformerEncoder(layer, layers)
        self.norm = nn.LayerNorm(dim)

    def forward(self, maps: Tensor, wireless_context: Tensor, origin: Tensor, resolution: float) -> tuple[Tensor, Tensor]:
        batch, channels, rows, columns = maps.shape
        pooled = F.adaptive_avg_pool2d(maps, (self.grid_size, self.grid_size))
        y, x = torch.meshgrid(
            torch.arange(self.grid_size, device=maps.device),
            torch.arange(self.grid_size, device=maps.device),
            indexing="ij",
        )
        scale_x = columns / self.grid_size * float(resolution)
        scale_y = rows / self.grid_size * float(resolution)
        xy = torch.stack(((x + 0.5) * scale_x, (y + 0.5) * scale_y), dim=-1).reshape(1, -1, 2)
        xy = xy + origin[:, None, :]
        height = pooled[:, 1:2].flatten(2).transpose(1, 2) if channels > 1 else torch.zeros(batch, self.grid_size**2, 1, device=maps.device)
        xyz = torch.cat((xy.expand(batch, -1, -1), height), dim=-1)
        features = pooled.flatten(2).transpose(1, 2)
        tokens = self.map_projection(torch.cat((features, xyz), dim=-1))
        tokens = tokens + self.tx_projection(wireless_context)[:, None]
        return self.norm(self.encoder(tokens)), xyz


class RayCorridorDecoder(nn.Module):
    def __init__(self, dim: int, heads: int, corridor_tokens: int):
        super().__init__()
        self.corridor_tokens = int(corridor_tokens)
        self.query = nn.Sequential(nn.Linear(10, dim), nn.GELU(), nn.Linear(dim, dim))
        self.attention = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.power = nn.Sequential(nn.Linear(2 * dim, dim), nn.GELU(), nn.Linear(dim, 1))

    def forward(self, memory: Tensor, voxel_xyz: Tensor, tx_xyz: Tensor, rx_xy: Tensor) -> tuple[Tensor, Tensor]:
        rx_xyz = torch.cat((rx_xy, torch.full_like(rx_xy[:, :1], 1.5)), dim=1)
        segment = rx_xyz - tx_xyz
        relative = voxel_xyz - tx_xyz[:, None]
        projection = torch.sum(relative * segment[:, None], dim=-1) / torch.sum(segment**2, dim=-1, keepdim=True).clamp_min(1e-8)
        projection = projection.clamp(0.0, 1.0)
        nearest = tx_xyz[:, None] + projection[..., None] * segment[:, None]
        distance = torch.linalg.vector_norm(voxel_xyz - nearest, dim=-1)
        count = min(self.corridor_tokens, memory.shape[1])
        indices = torch.topk(distance, count, largest=False, dim=1).indices
        corridor = torch.gather(memory, 1, indices[..., None].expand(-1, -1, memory.shape[-1]))
        geometry = torch.cat((tx_xyz, rx_xyz, segment, torch.linalg.vector_norm(segment, dim=1, keepdim=True)), dim=1)
        query = self.query(geometry)[:, None]
        attended, _ = self.attention(query, corridor, corridor, need_weights=False)
        fused = torch.cat((query[:, 0], attended[:, 0]), dim=1)
        return self.power(fused)[:, 0], fused


class CIRSetDecoder(nn.Module):
    def __init__(self, fused_dim: int, subcarriers: int, antennas: int, tap_count: int):
        super().__init__()
        self.subcarriers = int(subcarriers)
        self.antennas = int(antennas)
        self.tap_count = int(tap_count)
        self.taps = nn.Sequential(
            nn.Linear(fused_dim, fused_dim),
            nn.GELU(),
            nn.Linear(fused_dim, tap_count * 4),
        )
        self.array_response = nn.Parameter(torch.zeros(antennas, dtype=torch.float32))

    def forward(self, fused: Tensor) -> Tensor:
        values = self.taps(fused).reshape(-1, self.tap_count, 4)
        existence = torch.sigmoid(values[..., 0])
        delay = torch.sigmoid(values[..., 1])
        amplitude = torch.complex(values[..., 2], values[..., 3]) * existence
        frequency = torch.linspace(0.0, 1.0, self.subcarriers, device=fused.device)
        phase = torch.exp(-2j * math.pi * delay[..., None] * frequency)
        scalar = torch.sum(amplitude[..., None] * phase, dim=1)
        array = torch.exp(1j * self.array_response)[None, :, None]
        return (array * scalar[:, None]).reshape(fused.shape[0], -1)


class WiSERForward(nn.Module):
    """Sparse scene memory with ray-corridor radiomap and DETR-style tap readouts."""

    def __init__(self, map_channels: int, context_dim: int, dim: int, heads: int, layers: int, grid_size: int, corridor_tokens: int, antennas: int, subcarriers: int, tap_count: int):
        super().__init__()
        self.scene = SparseSceneEncoder(map_channels, context_dim, dim, heads, layers, grid_size)
        self.radiomap = RayCorridorDecoder(dim, heads, corridor_tokens)
        self.cir = CIRSetDecoder(2 * dim, subcarriers, antennas, tap_count)

    def forward(self, maps: Tensor, tx_xyz: Tensor, wireless_context: Tensor, rx_xy: Tensor, origin: Tensor, resolution: float) -> tuple[Tensor, Tensor]:
        memory, voxel_xyz = self.scene(maps, wireless_context, origin, resolution)
        power, fused = self.radiomap(memory, voxel_xyz, tx_xyz, rx_xy)
        return power, self.cir(fused)

    def training_loss(self, csi: Tensor, maps: Tensor, tx_xyz: Tensor, wireless_context: Tensor, rx_xy: Tensor, origin: Tensor, resolution: float) -> Tensor:
        predicted_power, predicted_csi = self(maps, tx_xyz, wireless_context, rx_xy, origin, resolution)
        target_complex = complex_csi(csi)
        target_power = 10.0 * torch.log10(torch.mean(target_complex.abs() ** 2, dim=1).clamp_min(1e-12))
        power_loss = F.huber_loss(predicted_power, target_power)
        csi_scale = torch.sqrt(torch.mean(target_complex.abs() ** 2, dim=1, keepdim=True).clamp_min(1e-12))
        csi_loss = torch.mean(torch.abs(predicted_csi / csi_scale - target_complex / csi_scale) ** 2)
        return power_loss + csi_loss


class RFIRForward(nn.Module):
    """Differentiable 2.5D RF-BSDF renderer over map-cell Gaussian primitives."""

    def __init__(self, material_count: int, antennas: int, subcarriers: int, context_dim: int, hidden: int, maximum_primitives: int):
        super().__init__()
        self.material_reflection = nn.Embedding(material_count, 2)
        self.material_roughness = nn.Embedding(material_count, 1)
        self.attenuation = nn.Sequential(nn.Linear(5, hidden), nn.GELU(), nn.Linear(hidden, 2))
        self.array_phase = nn.Parameter(torch.zeros(antennas))
        self.context_modulation = nn.Sequential(
            nn.Linear(context_dim, hidden), nn.GELU(), nn.Linear(hidden, 2 * subcarriers)
        )
        self.subcarriers = int(subcarriers)
        self.maximum_primitives = int(maximum_primitives)

    def _primitives(self, maps: Tensor, origin: Tensor, resolution: float) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        batch, _, rows, columns = maps.shape
        occupancy = maps[:, 0] > 0.5
        height = maps[:, 1]
        material = maps[:, 2].round().long().clamp_min(0)
        y, x = torch.meshgrid(
            torch.arange(rows, device=maps.device), torch.arange(columns, device=maps.device), indexing="ij"
        )
        centers_xy = torch.stack(((x + 0.5) * resolution, (y + 0.5) * resolution), dim=-1).reshape(-1, 2)
        centers = []
        materials = []
        valid = []
        areas = []
        for index in range(batch):
            selected = torch.nonzero(occupancy[index].flatten(), as_tuple=False).flatten()[: self.maximum_primitives]
            count = selected.numel()
            pad = self.maximum_primitives - count
            xyz = torch.cat((centers_xy[selected] + origin[index], height[index].flatten()[selected, None]), dim=1)
            xyz = F.pad(xyz, (0, 0, 0, pad))
            mat = F.pad(material[index].flatten()[selected], (0, pad))
            mask = torch.cat((torch.ones(count, device=maps.device), torch.zeros(pad, device=maps.device)))
            area = mask * (resolution**2)
            centers.append(xyz)
            materials.append(mat)
            valid.append(mask)
            areas.append(area)
        return torch.stack(centers), torch.stack(materials), torch.stack(valid), torch.stack(areas)

    def forward(self, maps: Tensor, tx_xyz: Tensor, wireless_context: Tensor, rx_xy: Tensor, origin: Tensor, resolution: float) -> Tensor:
        rx_xyz = torch.cat((rx_xy, torch.full_like(rx_xy[:, :1], 1.5)), dim=1)
        centers, material, valid, area = self._primitives(maps, origin, resolution)
        tx_leg = centers - tx_xyz[:, None]
        rx_leg = rx_xyz[:, None] - centers
        d_tx = torch.linalg.vector_norm(tx_leg, dim=-1).clamp_min(0.25)
        d_rx = torch.linalg.vector_norm(rx_leg, dim=-1).clamp_min(0.25)
        direct_distance = torch.linalg.vector_norm(rx_xyz - tx_xyz, dim=-1).clamp_min(0.25)
        reflection_raw = self.material_reflection(material)
        reflection = torch.complex(reflection_raw[..., 0], reflection_raw[..., 1])
        roughness = F.softplus(self.material_roughness(material)[..., 0])
        incidence = torch.abs(tx_leg[..., 2]) / d_tx
        departure = torch.abs(rx_leg[..., 2]) / d_rx
        directional = torch.pow((incidence * departure).clamp_min(1e-4), 1.0 + roughness)
        geometry = torch.stack((d_tx, d_rx, incidence, departure, roughness), dim=-1)
        attenuation = self.attenuation(geometry)
        attenuation_complex = torch.complex(attenuation[..., 0], attenuation[..., 1])
        scatter_amplitude = valid * area * directional / (d_tx * d_rx)
        frequency = torch.linspace(0.0, 1.0, self.subcarriers, device=maps.device)
        scatter_phase = torch.exp(-2j * math.pi * (d_tx + d_rx)[..., None] * frequency / 10.0)
        scattered = torch.sum(
            scatter_amplitude[..., None] * reflection[..., None] * attenuation_complex[..., None] * scatter_phase,
            dim=1,
        )
        direct_phase = torch.exp(-2j * math.pi * direct_distance[:, None] * frequency / 10.0)
        direct = direct_phase / direct_distance[:, None]
        modulation = self.context_modulation(wireless_context).reshape(-1, self.subcarriers, 2)
        modulation = 1.0 + 0.1 * torch.complex(modulation[..., 0], modulation[..., 1])
        scalar = (direct + scattered) * modulation
        array = torch.exp(1j * self.array_phase)[None, :, None]
        return (array * scalar[:, None]).reshape(maps.shape[0], -1)

    def training_loss(self, csi: Tensor, maps: Tensor, tx_xyz: Tensor, wireless_context: Tensor, rx_xy: Tensor, origin: Tensor, resolution: float) -> Tensor:
        prediction = self(maps, tx_xyz, wireless_context, rx_xy, origin, resolution)
        target = complex_csi(csi)
        scale = torch.sqrt(torch.mean(target.abs() ** 2, dim=1, keepdim=True).clamp_min(1e-12))
        signal_loss = torch.mean(torch.abs(prediction / scale - target / scale) ** 2)
        power_loss = F.huber_loss(
            10.0 * torch.log10(torch.mean(prediction.abs() ** 2, dim=1).clamp_min(1e-12)),
            10.0 * torch.log10(torch.mean(target.abs() ** 2, dim=1).clamp_min(1e-12)),
        )
        return signal_loss + power_loss
