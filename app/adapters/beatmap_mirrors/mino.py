import logging

from app.adapters.beatmap_mirrors import BeatmapMirror


class MinoMirror(BeatmapMirror):
    base_url = "https://catboy.best"

    async def fetch_beatmap_zip_data(self, beatmapset_id: int) -> bytes | None:
        try:
            logging.info(f"Fetching beatmapset osz2 from mino: {beatmapset_id}")
            response = await self.http_client.get(
                f"{self.base_url}/d/{beatmapset_id}",
            )
            response.raise_for_status()
            return response.read()
        except Exception:
            logging.warning(
                "Failed to fetch beatmap from catboy.best",
                exc_info=True,
            )
            return None