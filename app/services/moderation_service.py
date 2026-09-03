from __future__ import annotations

import os
import random
import re
import shutil
import tempfile
from pathlib import Path

import discord
from python_pt_dictionary import dictionary

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


VIDEO_QUALITY_LIMITS = [1080, 720, 480, 360, 240, 144]


class ModerationService:
    def __init__(self, context):
        self.context = context

    def parse_duration(self, duration: str) -> int:
        match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", duration)
        if not match:
            return 0
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds

    def format_duration(self, seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if hours > 0:
            parts.append(f"{hours} horas")
        if minutes > 0:
            parts.append(f"{minutes} minutos")
        if seconds > 0:
            parts.append(f"{seconds} segundos")
        return ", ".join(parts) if parts else "0 segundos"

    def _download_youtube(self, link: str, download_dir: str, max_height: int) -> tuple[str, str]:
        if yt_dlp is None:
            raise RuntimeError("yt-dlp nao esta instalado. Rode: pip install yt-dlp")

        options = {
            "format": (
                f"best[ext=mp4][height<={max_height}]/"
                f"best[height<={max_height}]/worst[ext=mp4]/worst"
            ),
            "noplaylist": True,
            "outtmpl": os.path.join(download_dir, "%(title).80s [%(id)s].%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(link, download=True)
            video_path = downloader.prepare_filename(info)

        if not os.path.exists(video_path):
            downloaded_files = [path for path in Path(download_dir).iterdir() if path.is_file()]
            if not downloaded_files:
                raise RuntimeError("download finalizou, mas nenhum arquivo foi encontrado.")
            video_path = str(max(downloaded_files, key=lambda path: path.stat().st_mtime))
        return video_path, str(info.get("title") or "video")

    def download_video_until_limit(self, link: str, max_size: int) -> tuple[str, str, int, str]:
        download_dir = tempfile.mkdtemp(prefix="yungbot_video_")
        last_size = 0
        try:
            for max_height in VIDEO_QUALITY_LIMITS:
                for downloaded_file in Path(download_dir).iterdir():
                    if downloaded_file.is_file():
                        downloaded_file.unlink(missing_ok=True)
                video_path, title = self._download_youtube(link, download_dir, max_height)
                last_size = os.path.getsize(video_path)
                print(f"[video] tentativa {max_height}p: {last_size / 1024 / 1024:.1f} MB")
                if last_size <= max_size:
                    return video_path, title, max_height, download_dir
            raise RuntimeError(
                "nao consegui baixar uma versao pequena o suficiente para o limite do servidor "
                f"({last_size / 1024 / 1024:.1f} MB > {max_size / 1024 / 1024:.1f} MB)."
            )
        except Exception:
            shutil.rmtree(download_dir, ignore_errors=True)
            raise

    async def send_log(self, content: str) -> None:
        channel_id = self.context.config.log_channel_id
        if not channel_id:
            return
        channel = self.context.bot.get_channel(int(channel_id))
        if channel:
            await channel.send(content)

    async def mute_member(self, member, guild, duration: str, reason: str):
        if not self.context.config.mute_role_id:
            return None
        mute_role = discord.utils.get(guild.roles, id=int(self.context.config.mute_role_id))
        if not mute_role:
            return None
        seconds = self.parse_duration(duration)
        if seconds == 0:
            return 0, None

        await member.add_roles(mute_role)
        formatted = self.format_duration(seconds)
        log_message = f"{member.mention} foi mutado por {formatted}. Motivo: {reason}"
        await self.send_log(log_message)
        return seconds, (mute_role, formatted)

    async def unmute_member(self, member, guild) -> bool | None:
        if not self.context.config.mute_role_id:
            return None
        mute_role = discord.utils.get(guild.roles, id=int(self.context.config.mute_role_id))
        if not mute_role:
            return None
        if mute_role not in member.roles:
            return False
        await member.remove_roles(mute_role)
        await self.send_log(f"{member.mention} foi desmutado.")
        return True

    def divine_message(self, word_count: int) -> str:
        alphabet = self.context.word.alphabet
        sentence = ""
        seed = random.randint(0, 10000)
        for _ in range(word_count):
            seed += 1
            random.seed(seed)
            new_word = None
            while new_word is None or not new_word:
                candidate = "".join(random.choices(alphabet, k=5))
                for _ in range(4):
                    candidate = candidate.replace(random.choice(alphabet), "", 1)
                if candidate:
                    new_word = dictionary.select(candidate, dictionary.Selector.PREFIX)
            sentence += " " + str.lower(new_word[random.randrange(len(new_word))].text)
        return sentence.strip()
