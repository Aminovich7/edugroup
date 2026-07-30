"""Dars davomiyligi 300–600 soniya, video havolasi esa kinescope.io bo'lishi shart."""

import pytest

from tests.conftest import auth_headers
from tests.factories import create_course, create_group, create_teacher

BASE_LESSON = {
    "title": "Test dars",
    "kinescope_video_id": "abc123",
    "kinescope_url": "https://kinescope.io/abc123",
    "duration_seconds": 420,
    "order_index": 1,
}


async def _create_group_with_teacher(session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    return teacher, group


@pytest.mark.parametrize("duration", [299, 601, 60, 3600])
async def test_duration_outside_range_returns_422(client, session, duration):
    teacher, group = await _create_group_with_teacher(session)

    response = await client.post(
        f"/api/groups/{group.id}/lessons",
        json={**BASE_LESSON, "duration_seconds": duration},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("duration", [300, 450, 600])
async def test_duration_inside_range_is_accepted(client, session, duration):
    teacher, group = await _create_group_with_teacher(session)

    response = await client.post(
        f"/api/groups/{group.id}/lessons",
        json={**BASE_LESSON, "duration_seconds": duration},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 201


async def test_non_kinescope_url_returns_422(client, session):
    teacher, group = await _create_group_with_teacher(session)

    response = await client.post(
        f"/api/groups/{group.id}/lessons",
        json={**BASE_LESSON, "kinescope_url": "https://youtube.com/watch?v=abc"},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 422
