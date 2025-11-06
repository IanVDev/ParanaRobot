"""Unzip helper responsible for preparing FHML files for validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import logging
import shutil
import zipfile

from .utils import FileMetadata, timestamped_tempdir

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Outcome of an extraction step."""

    metadata: Optional[FileMetadata]
    error: Optional[str] = None


class Unzipper:
    """Extract `.zip` payloads and stage `.d` files for validation."""

    def extract(self, input_path: Path) -> ExtractionResult:
        input_path = input_path.expanduser().resolve()
        if not input_path.exists():
            return ExtractionResult(metadata=None, error=f"Arquivo não encontrado: {input_path}")

        temp_dir = timestamped_tempdir()

        if zipfile.is_zipfile(input_path):
            logger.info("Descompactando %s", input_path)
            return self._extract_zip(input_path, temp_dir)

        return self._stage_plain_file(input_path, temp_dir)

    def _extract_zip(self, zip_path: Path, temp_dir: Path) -> ExtractionResult:
        try:
            with zipfile.ZipFile(zip_path) as zf:
                members = [m for m in zf.namelist() if not m.endswith("/")]
                if not members:
                    return ExtractionResult(metadata=None, error="Arquivo ZIP vazio")
                extracted_files = []
                for member in members:
                    target = temp_dir / Path(member).name
                    logger.debug("Extraindo %s para %s", member, target)
                    with zf.open(member) as source, target.open("wb") as handle:
                        shutil.copyfileobj(source, handle)
                    extracted_files.append(target)
        except zipfile.BadZipFile as exc:
            return ExtractionResult(metadata=None, error=f"ZIP inválido: {exc}")

        target_file = self._select_candidate(extracted_files)
        if not target_file:
            return ExtractionResult(
                metadata=None,
                error="Nenhum arquivo `.d` encontrado dentro do ZIP",
            )

        metadata = FileMetadata(
            original_path=zip_path,
            working_path=target_file,
            temp_dir=temp_dir,
            extracted_from_zip=True,
        )
        return ExtractionResult(metadata=metadata)

    def _stage_plain_file(self, file_path: Path, temp_dir: Path) -> ExtractionResult:
        target = temp_dir / file_path.name
        shutil.copy(file_path, target)

        metadata = FileMetadata(
            original_path=file_path,
            working_path=target,
            temp_dir=temp_dir,
            extracted_from_zip=False,
        )
        return ExtractionResult(metadata=metadata)

    @staticmethod
    def _select_candidate(files: list[Path]) -> Optional[Path]:
        """Select the `.d` candidate or fallback to the first file."""

        if not files:
            return None
        d_files = [path for path in files if path.suffix.lower() == ".d"]
        if len(d_files) == 1:
            return d_files[0]
        if len(d_files) > 1:
            logger.warning("Múltiplos arquivos `.d` encontrados; usando o primeiro: %s", d_files[0])
            return d_files[0]
        logger.warning("Nenhum `.d` explícito encontrado; assumindo %s", files[0])
        return files[0]


__all__ = ["ExtractionResult", "Unzipper"]
