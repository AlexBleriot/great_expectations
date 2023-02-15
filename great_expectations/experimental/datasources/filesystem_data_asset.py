from __future__ import annotations

import copy
import logging
import pathlib
from typing import TYPE_CHECKING, Optional

import great_expectations.exceptions as ge_exceptions
from great_expectations.core.batch_spec import PathBatchSpec
from great_expectations.experimental.datasources.file_path_data_asset import (
    _FilePathDataAsset,
)
from great_expectations.experimental.datasources.interfaces import (
    Batch,
    BatchRequest,
    BatchRequestOptions,
    TestConnectionError,
)

if TYPE_CHECKING:
    from great_expectations.execution_engine import (
        PandasExecutionEngine,
        SparkDFExecutionEngine,
    )

logger = logging.getLogger(__name__)


class _FilesystemDataAsset(_FilePathDataAsset):
    def _get_reader_method(self) -> str:
        raise NotImplementedError(
            """One needs to explicitly provide "reader_method" for Filesystem DataAsset extensions as temporary \
work-around, until "type" naming convention and method for obtaining 'reader_method' from it are established."""
        )

    def _get_reader_options_include(self) -> set[str] | None:
        raise NotImplementedError(
            """One needs to explicitly provide set(str)-valued reader options for "pydantic.BaseModel.dict()" method \
to use as its "include" directive for Filesystem style DataAsset processing."""
        )

    def test_connection(self) -> None:
        """Test the connection for the CSVAsset.

        Raises:
            TestConnectionError: If the connection test fails.
        """
        success = False
        for filepath in self.datasource.base_directory.glob("**/*.*"):
            if self.regex.match(
                str(filepath.relative_to(self.datasource.base_directory))
            ):
                # if one file in the path matches the regex, we consider this asset valid
                success = True
                break
        if not success:
            raise TestConnectionError(
                f"No file at path: {self.datasource.base_directory.resolve()} matched the regex: {self.regex.pattern}"
            )

    def _fully_specified_batch_requests_with_path(
        self, batch_request: BatchRequest
    ) -> list[tuple[BatchRequest, pathlib.Path]]:
        """Generates a list fully specified batch requests from partial specified batch request

        Args:
            batch_request: A batch request

        Returns:
            A list of pairs (batch_request, path) where 'batch_request' is a fully specified
            batch request and 'path' is the path to the corresponding file on disk.
            This list will be empty if no files exist on disk that correspond to the input
            batch request.
        """
        base_directory: pathlib.Path = self.datasource.base_directory
        all_paths: list[pathlib.Path] = [
            pathlib.Path(path) for path in base_directory.glob("**/*.*")
        ]

        batch_requests_with_path: list[tuple[BatchRequest, pathlib.Path]] = []

        abs_path: pathlib.Path
        for abs_path in all_paths:
            path_relative_to_base_dir = str(abs_path.relative_to(base_directory))
            match = self._regex_parser.get_matches(target=path_relative_to_base_dir)
            if match:
                # Create the batch request that would correlate to this regex match
                match_options = {}
                for group_id in range(
                    1, self._regex_parser.get_num_all_matched_group_values() + 1
                ):
                    match_options[
                        self._all_group_index_to_group_name_mapping[group_id]
                    ] = match.group(group_id)
                    match_options["path"] = str(abs_path)
                # Determine if this file_name matches the batch_request
                allowed_match = True
                for key, value in batch_request.options.items():
                    if match_options[key] != value:
                        allowed_match = False
                        break
                if allowed_match:
                    batch_requests_with_path.append(
                        (
                            BatchRequest(
                                datasource_name=self.datasource.name,
                                data_asset_name=self.name,
                                options=match_options,
                            ),
                            abs_path,
                        )
                    )
                    logger.debug(f"Matching path: {abs_path}")
        if not batch_requests_with_path:
            logger.warning(
                f"Batch request {batch_request} corresponds to no data files."
            )
        return batch_requests_with_path

    def batch_request_options_template(
        self,
    ) -> BatchRequestOptions:
        idx: int
        batch_request_options_template = {idx: None for idx in self._all_group_names}
        batch_request_options_template["path"] = None
        return batch_request_options_template

    def build_batch_request(
        self, options: Optional[BatchRequestOptions] = None
    ) -> BatchRequest:
        if options:
            for option, value in options.items():
                if (
                    option in self._all_group_name_to_group_index_mapping
                    and not isinstance(value, str)
                ):
                    raise ge_exceptions.InvalidBatchRequestError(
                        f"All regex matching options must be strings. The value of '{option}' is "
                        f"not a string: {value}"
                    )
        return super().build_batch_request(options)

    def get_batch_list_from_batch_request(
        self, batch_request: BatchRequest
    ) -> list[Batch]:
        self._validate_batch_request(batch_request)
        batch_list: list[Batch] = []

        kwargs: dict | None = getattr(self, "kwargs", None)
        if not kwargs:
            kwargs = {}

        for request, path in self._fully_specified_batch_requests_with_path(
            batch_request
        ):
            batch_spec = PathBatchSpec(
                path=str(path),
                reader_method=self._get_reader_method(),
                reader_options=self.dict(
                    include=self._get_reader_options_include(),
                    exclude=self._EXCLUDE_FROM_READER_OPTIONS,
                    exclude_unset=True,
                    by_alias=True,
                    **kwargs,
                ),
            )
            execution_engine: PandasExecutionEngine | SparkDFExecutionEngine = (
                self.datasource.get_execution_engine()
            )
            data, markers = execution_engine.get_batch_data_and_markers(
                batch_spec=batch_spec
            )

            # batch_definition (along with batch_spec and markers) is only here to satisfy a
            # legacy constraint when computing usage statistics in a validator. We hope to remove
            # it in the future.
            # imports are done inline to prevent a circular dependency with core/batch.py
            from great_expectations.core import IDDict
            from great_expectations.core.batch import BatchDefinition

            batch_definition = BatchDefinition(
                datasource_name=self.datasource.name,
                data_connector_name="experimental",
                data_asset_name=self.name,
                batch_identifiers=IDDict(request.options),
                batch_spec_passthrough=None,
            )

            batch_metadata = copy.deepcopy(request.options)
            batch_metadata["base_directory"] = path

            # Some pydantic annotations are postponed due to circular imports.
            # Batch.update_forward_refs() will set the annotations before we
            # instantiate the Batch class since we can import them in this scope.
            Batch.update_forward_refs()
            batch_list.append(
                Batch(
                    datasource=self.datasource,
                    data_asset=self,
                    batch_request=request,
                    data=data,
                    metadata=batch_metadata,
                    legacy_batch_markers=markers,
                    legacy_batch_spec=batch_spec,
                    legacy_batch_definition=batch_definition,
                )
            )
        self.sort_batches(batch_list)
        return batch_list
