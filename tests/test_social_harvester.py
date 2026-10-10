"""Tests for Multimodal Social Flyer & Animation Harvester (Task 7.1)."""

import os
from pathlib import Path
import pytest
from PIL import Image

from shadenet.towncrier.social_harvester import (
    classify_media,
    is_animated,
    is_motion_media,
    extract_listings_from_file,
    _cache_image,
    CORE_VENUES,
)


@pytest.fixture
def sample_png_flyer(tmp_path):
    img_path = tmp_path / "flyer.png"
    im = Image.new("RGB", (640, 480), color=(30, 30, 35))
    im.save(img_path, format="PNG")
    return img_path


@pytest.fixture
def sample_gif_story(tmp_path):
    gif_path = tmp_path / "story.gif"
    frames = [
        Image.new("RGB", (320, 480), color=(20, 20, 20)),
        Image.new("RGB", (320, 480), color=(40, 40, 40)),
    ]
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=200,
        loop=0,
        format="GIF",
    )
    return gif_path


def test_classify_media_types(sample_png_flyer, sample_gif_story, tmp_path):
    assert classify_media(sample_png_flyer) == "png"
    assert classify_media(sample_gif_story) == "gif"

    jpg_path = tmp_path / "poster.jpg"
    Image.new("RGB", (100, 100), color=(255, 0, 0)).save(jpg_path, format="JPEG")
    assert classify_media(jpg_path) == "jpeg"


def test_animated_motion_detection(sample_png_flyer, sample_gif_story):
    assert is_animated(sample_gif_story) is True
    assert is_motion_media(sample_gif_story) is True

    assert is_animated(sample_png_flyer) is False
    assert is_motion_media(sample_png_flyer) is False


def test_core_venues_coverage():
    assert "arlene-francis-center" in CORE_VENUES
    assert "vintage-space" in CORE_VENUES
    assert "shady-oak-barrel-house" in CORE_VENUES
    assert "3-disciples-brewing" in CORE_VENUES
    assert "barrel-brothers" in CORE_VENUES
    for key, v in CORE_VENUES.items():
        assert "name" in v
        assert "sources" in v
        assert len(v["sources"]) >= 1


def test_image_caching(tmp_path):
    im = Image.new("RGB", (200, 200), color=(100, 150, 200))
    cached = _cache_image(im, ext="png")
    assert cached.exists()
    assert cached.is_file()
    assert cached.suffix == ".png"


def test_extract_listings_from_flyer_file(sample_png_flyer):
    listings = extract_listings_from_file(
        sample_png_flyer,
        source_url="https://instagram.com/p/sample123",
        source_handle="@arlenefranciscenter",
        attribution={"handle": "@arlenefranciscenter", "source": "instagram"},
    )
    # Yields valid structure with attribution
    for l in listings:
        assert "title" in l
        assert "venue_id" in l
        assert "attribution" in l
        assert l["attribution"]["handle"] == "@arlenefranciscenter"
