from __future__ import annotations

import logging
import pathlib
import re
from typing import List, Optional

from great_expectations.core._docs_decorators import public_api
from great_expectations.experimental.datasources.data_asset.data_connector.file_path_data_connector import (
    FilePathDataConnector,
)
from great_expectations.experimental.datasources.data_asset.data_connector.util import (
    get_filesystem_one_level_directory_glob_path_list,
    normalize_directory_path,
)

logger = logging.getLogger(__name__)


@public_api
class FilesystemDataConnector(FilePathDataConnector):
    """Extension of ConfiguredAssetFilePathDataConnector used to connect to Filesystem.

    Being a Configured Asset Data Connector, it requires an explicit list of each Data Asset it can
    connect to. While this allows for fine-grained control over which Data Assets may be accessed,
    it requires more setup.

    Args:
        name (str): name of ConfiguredAssetFilesystemDataConnector
        regex (pattern): Optional regex pattern for filtering data references
        glob_directive (str): glob for selecting files in directory (defaults to `**/*`) or nested directories (e.g. `*/*/*.csv`)
        # TODO: <Alex>ALEX</Alex>
        # sorters (list): Optional list if you want to sort the data_references
        # TODO: <Alex>ALEX</Alex>
    """

    def __init__(
        self,
        name: str,
        datasource_name: str,
        data_asset_name: str,
        execution_engine_name: str,
        base_directory: pathlib.Path,
        regex: Optional[re.Pattern] = None,
        glob_directive: str = "**/*",
        # TODO: <Alex>ALEX</Alex>
        # sorters: Optional[list] = None,
        # TODO: <Alex>ALEX</Alex>
    ) -> None:
        super().__init__(
            name=name,
            datasource_name=datasource_name,
            data_asset_name=data_asset_name,
            execution_engine_name=execution_engine_name,
            regex=regex,
            # TODO: <Alex>ALEX</Alex>
            # sorters=sorters,
            # TODO: <Alex>ALEX</Alex>
        )

        self._base_directory = base_directory
        self._glob_directive: str = glob_directive

    @property
    def base_directory(self) -> str:
        """
        Accessor method for base_directory. If directory is a relative path, interpret it as relative to the
        root directory. If it is absolute, then keep as-is.
        """
        return normalize_directory_path(
            dir_path=str(self._base_directory),
            root_directory_path=self.data_context_root_directory,
        )

    def _get_data_reference_list(self) -> List[str]:
        base_directory: str = self.base_directory
        glob_directive: str = self._glob_directive
        path_list: List[str] = get_filesystem_one_level_directory_glob_path_list(
            base_directory_path=base_directory, glob_directive=glob_directive
        )
        return sorted(path_list)

    def _get_full_file_path(self, path: str) -> str:
        base_directory: str = self.base_directory
        return str(pathlib.Path(base_directory).joinpath(path))