#!/usr/bin/env python3
"""Build a soft chroma matte and recover foreground color at keyed edges."""

from __future__ import annotations

import numpy as np
from PIL import Image

ALGORITHM = "border-connected-soft-chroma-matte-v2"


def dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask
    for _ in range(max(0, iterations)):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        result = (
            padded[1:-1, 1:-1]
            | padded[:-2, 1:-1]
            | padded[2:, 1:-1]
            | padded[1:-1, :-2]
            | padded[1:-1, 2:]
            | padded[:-2, :-2]
            | padded[:-2, 2:]
            | padded[2:, :-2]
            | padded[2:, 2:]
        )
    return result


def erode(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask
    for _ in range(max(0, iterations)):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        result = (
            padded[1:-1, 1:-1]
            & padded[:-2, 1:-1]
            & padded[2:, 1:-1]
            & padded[1:-1, :-2]
            & padded[1:-1, 2:]
            & padded[:-2, :-2]
            & padded[:-2, 2:]
            & padded[2:, :-2]
            & padded[2:, 2:]
        )
    return result


def border_connected(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    connected = np.zeros_like(mask, dtype=bool)
    stack: list[tuple[int, int]] = []
    for x in range(width):
        if mask[0, x]:
            stack.append((x, 0))
        if mask[height - 1, x]:
            stack.append((x, height - 1))
    for y in range(height):
        if mask[y, 0]:
            stack.append((0, y))
        if mask[y, width - 1]:
            stack.append((width - 1, y))

    while stack:
        x, y = stack.pop()
        if connected[y, x] or not mask[y, x]:
            continue
        connected[y, x] = True
        if x > 0:
            stack.append((x - 1, y))
        if x + 1 < width:
            stack.append((x + 1, y))
        if y > 0:
            stack.append((x, y - 1))
        if y + 1 < height:
            stack.append((x, y + 1))
    return connected


def _key_channel_masks(key: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    high = key > 160
    low = key < 96
    if not high.any():
        high = key == key.max()
    if not low.any():
        low = ~high
    if not low.any():
        low = key == key.min()
    return high, low


def _srgb_to_linear(values: np.ndarray) -> np.ndarray:
    values = values / 255.0
    return np.where(
        values <= 0.04045,
        values / 12.92,
        ((values + 0.055) / 1.055) ** 2.4,
    )


def _linear_to_srgb(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0.0, 1.0)
    return np.where(
        values <= 0.0031308,
        values * 12.92,
        1.055 * values ** (1 / 2.4) - 0.055,
    ) * 255.0


def key_family_mask(
    rgb: np.ndarray,
    chroma_key: tuple[int, int, int],
    *,
    minimum_dominance: float = 10.0,
    minimum_similarity: float = 0.82,
) -> np.ndarray:
    """Return pixels whose chroma direction and channel dominance match the key."""
    values = rgb.astype(np.float32)
    key = np.array(chroma_key, dtype=np.float32)
    high, low = _key_channel_masks(key)
    key_mean = values[:, :, high].mean(axis=2)
    non_key_mean = values[:, :, low].mean(axis=2)
    dominance = key_mean - non_key_mean

    centered = values - values.mean(axis=2, keepdims=True)
    key_centered = key - key.mean()
    denominator = np.linalg.norm(centered, axis=2) * np.linalg.norm(key_centered)
    numerator = np.sum(centered * key_centered, axis=2)
    similarity = np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, -1.0),
        where=denominator > 1e-6,
    )
    return (dominance >= minimum_dominance) & (similarity >= minimum_similarity)


def matte_chroma_background(
    image: Image.Image,
    *,
    chroma_key: tuple[int, int, int],
    threshold: float = 72.0,
    softness: float = 96.0,
    edge_iterations: int = 2,
    despill_margin: float = 16.0,
) -> tuple[Image.Image, dict[str, object]]:
    """Remove a generated chroma backdrop without leaving colored edge pixels.

    The matte is seeded from key-like pixels connected to the image border, while
    exact key pixels are also cleared inside enclosed background gaps. Edge colors
    are unmixed from the key in linear light before the image is resized.
    """
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    if softness <= 0:
        raise ValueError("softness must be positive")
    if edge_iterations < 1:
        raise ValueError("edge_iterations must be at least 1")

    arr = np.array(image.convert("RGBA")).astype(np.float32)
    rgb = arr[:, :, :3]
    source_alpha = arr[:, :, 3] / 255.0
    key = np.array(chroma_key, dtype=np.float32)
    distance = np.sqrt(np.sum((rgb - key) ** 2, axis=2))
    high, low = _key_channel_masks(key)

    key_channel_mean = rgb[:, :, high].mean(axis=2)
    non_key_channel_mean = rgb[:, :, low].mean(axis=2)
    key_dominance = key_channel_mean - non_key_channel_mean
    channel_margin = max(72.0, threshold + softness * 0.45)

    high_match = np.ones(distance.shape, dtype=bool)
    for channel_index, is_key_channel in enumerate(high):
        if is_key_channel:
            high_match &= rgb[:, :, channel_index] >= key[channel_index] - channel_margin
    low_match = np.ones(distance.shape, dtype=bool)
    for channel_index, is_low_channel in enumerate(low):
        if is_low_channel:
            low_match &= rgb[:, :, channel_index] <= key[channel_index] + channel_margin

    candidate = (
        (distance < threshold + softness * 2.25)
        & high_match
        & low_match
        & (key_dominance > -18)
    )
    border_background = border_connected(candidate)
    confident_key = (distance <= threshold) & high_match & low_match
    background = border_background | confident_key
    background_band = dilate(background, edge_iterations + 2)

    alpha = source_alpha.copy()
    soft_alpha = np.clip((distance - threshold) / softness, 0.0, 1.0)
    alpha[background_band] = np.minimum(alpha[background_band], soft_alpha[background_band])
    alpha[background] = np.minimum(alpha[background], soft_alpha[background])

    chroma_family = background_band & (key_dominance > 18)
    alpha[chroma_family & (distance < threshold + softness * 1.4)] = 0.0

    foreground = alpha > (8 / 255)
    edge_band = dilate(foreground, edge_iterations) & ~erode(foreground, edge_iterations)
    low_alpha_chroma = background_band & edge_band & (alpha < 0.5) & (key_dominance > 10)
    alpha[low_alpha_chroma] = 0.0

    foreground = alpha > (8 / 255)
    edge_band = dilate(foreground, edge_iterations) & ~erode(foreground, edge_iterations)
    unmix_mask = (
        background_band
        & edge_band
        & (alpha > 0.08)
        & (alpha < 0.98)
        & (distance < threshold + softness * 3.0)
    )
    if unmix_mask.any():
        linear_rgb = _srgb_to_linear(rgb)
        linear_key = _srgb_to_linear(key)
        edge_alpha = alpha[:, :, None]
        linear_rgb[unmix_mask] = (
            linear_rgb[unmix_mask]
            - (1.0 - edge_alpha[unmix_mask]) * linear_key
        ) / np.maximum(edge_alpha[unmix_mask], 0.08)
        rgb[unmix_mask] = _linear_to_srgb(linear_rgb[unmix_mask])

    spill = background_band & edge_band & (key_dominance > despill_margin)
    if spill.any():
        channel_limit = non_key_channel_mean + despill_margin
        for channel_index, is_key_channel in enumerate(high):
            if is_key_channel:
                rgb[:, :, channel_index] = np.where(
                    spill,
                    np.minimum(rgb[:, :, channel_index], channel_limit),
                    rgb[:, :, channel_index],
                )

    out = np.zeros_like(arr, dtype=np.uint8)
    out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[:, :, 3] = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    out[out[:, :, 3] == 0, :3] = 0

    out_alpha = out[:, :, 3]
    remaining_key_family = key_family_mask(out[:, :, :3], chroma_key)
    visible = out_alpha > 8
    metrics: dict[str, object] = {
        "algorithm": ALGORITHM,
        "width": int(out.shape[1]),
        "height": int(out.shape[0]),
        "visible_pixels": int(visible.sum()),
        "border_background_pixels": int(border_background.sum()),
        "chroma_candidate_pixels": int(candidate.sum()),
        "soft_edge_pixels": int(((out_alpha > 0) & (out_alpha < 255)).sum()),
        "low_alpha_chroma_cleared_pixels": int(low_alpha_chroma.sum()),
        "unmixed_edge_pixels": int(unmix_mask.sum()),
        "despill_pixels": int(spill.sum()),
        "remaining_key_family_edge_pixels": int(
            (edge_band & visible & remaining_key_family).sum()
        ),
        "transparent_rgb_residue_pixels": int(
            ((out_alpha == 0) & np.any(out[:, :, :3] != 0, axis=2)).sum()
        ),
    }
    return Image.fromarray(out, mode="RGBA"), metrics
