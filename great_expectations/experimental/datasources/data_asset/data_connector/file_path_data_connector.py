from __future__ import annotations

import logging
import re
from abc import abstractmethod
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from great_expectations.core.batch_spec import BatchSpec, PathBatchSpec
from great_expectations.datasource.data_connector.batch_filter import (
    BatchFilter,
    build_batch_filter,
)
from great_expectations.datasource.data_connector.util import (
    map_batch_definition_to_data_reference_string_using_regex,
)
from great_expectations.experimental.datasources.data_asset.data_connector import (
    DataConnector,
)
from great_expectations.experimental.datasources.data_asset.data_connector.regex_parser import (
    RegExParser,
)

# TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
# TODO: <Alex>ALEX</Alex>
# from great_expectations.experimental.data_asset.data_connector.sorter import Sorter
# TODO: <Alex>ALEX</Alex>
from great_expectations.experimental.datasources.data_asset.data_connector.util import (
    batch_definition_matches_batch_request,
    map_data_reference_string_to_batch_definition_list_using_regex,
)

if TYPE_CHECKING:
    from great_expectations.core.batch import BatchDefinition
    from great_expectations.experimental.datasources.interfaces import BatchRequest


logger = logging.getLogger(__name__)


class FilePathDataConnector(DataConnector):
    """The base class for Data Connectors designed to access filesystem-like data.

    This can include traditional, disk-based filesystems or object stores such as S3, GCS, or Azure Blob Store.
    # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
    # TODO: <Alex>ALEX</Alex>
    # This class supports a regular expression and sorters for filtering and sorting data references.
    # TODO: <Alex>ALEX</Alex>

    See the `DataConnector` base class for more information on the role of Data Connectors.

    Note that `FilePathDataConnector` is not meant to be used on its own, but extended.

    Args:
        regex: A regex pattern for filtering data references
        # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
        # TODO: <Alex>ALEX</Alex>
        # sorters: A list of sorters for sorting data references.
        # TODO: <Alex>ALEX</Alex>
    """

    def __init__(
        self,
        datasource_name: str,
        data_asset_name: str,
        regex: re.Pattern,
        unnamed_regex_group_prefix: str = "batch_request_param_",
        # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
        # TODO: <Alex>ALEX</Alex>
        # sorters: Optional[list] = None,
        # TODO: <Alex>ALEX</Alex>
        file_path_template_map_fn: Optional[Callable] = None,
    ) -> None:
        super().__init__(
            datasource_name=datasource_name,
            data_asset_name=data_asset_name,
        )

        self._regex: re.Pattern = regex
        self._regex_parser: RegExParser = RegExParser(
            regex_pattern=regex, unnamed_regex_group_prefix=unnamed_regex_group_prefix
        )

        self._file_path_template_map_fn: Optional[Callable] = file_path_template_map_fn

        # This is a dictionary which maps data_references onto batch_requests.
        self._data_references_cache: Dict[str, List[BatchDefinition] | None] = {}

        self._refresh_data_references_cache()

    # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
    # TODO: <Alex>ALEX</Alex>
    # @property
    # def sorters(self) -> Optional[dict]:
    #     return self._sorters
    # TODO: <Alex>ALEX</Alex>

    # Interface Method
    def get_batch_definition_list_from_batch_request(
        self, batch_request: BatchRequest
    ) -> List[BatchDefinition]:
        """
        Retrieve batch_definitions and that match batch_request.

        First retrieves all batch_definitions that match batch_request
            - if batch_request also has a batch_filter, then select batch_definitions that match batch_filter.
            # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
            # TODO: <Alex>ALEX</Alex>
            # - if data_connector has sorters configured, then sort the batch_definition list before returning.
            # TODO: <Alex>ALEX</Alex>

        Args:
            batch_request (BatchRequest): BatchRequest (containing previously validated attributes) to process

        Returns:
            A list of BatchDefinition objects that match BatchRequest

        """
        if len(self._data_references_cache) == 0:
            self._refresh_data_references_cache()

        # Use a combination of a list and set to preserve iteration order
        batch_definition_list: List[BatchDefinition] = list()
        batch_definition_set = set()
        for batch_definition in self._get_batch_definition_list_from_cache():
            if (
                batch_definition_matches_batch_request(
                    batch_definition=batch_definition, batch_request=batch_request
                )
                and batch_definition not in batch_definition_set
            ):
                batch_definition_list.append(batch_definition)
                batch_definition_set.add(batch_definition)

        # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
        # TODO: <Alex>ALEX</Alex>
        # if self.sorters:
        #     batch_definition_list = self._sort_batch_definition_list(
        #         batch_definition_list=batch_definition_list
        #     )
        # TODO: <Alex>ALEX</Alex>

        if batch_request.options is not None:
            data_connector_query_dict = {
                "batch_filter_parameters": batch_request.options.copy()
            }
            # TODO: <Alex>ALEX-SUPPORT_LIMIT_BATCH_QUERY_OPTION_DIRECTIVE_LATER</Alex>
            # TODO: <Alex>ALEX</Alex>
            # if (
            #     batch_request.limit is not None
            #     and data_connector_query_dict.get("limit") is None
            # ):
            #     data_connector_query_dict["limit"] = batch_request.limit
            # TODO: <Alex>ALEX</Alex>

            batch_filter_obj: BatchFilter = build_batch_filter(
                data_connector_query_dict=data_connector_query_dict  # type: ignore[arg-type]
            )
            batch_definition_list = batch_filter_obj.select_from_data_connector_query(
                batch_definition_list=batch_definition_list
            )

        return batch_definition_list

    def build_batch_spec(self, batch_definition: BatchDefinition) -> PathBatchSpec:
        """
        Build BatchSpec from batch_definition by calling DataConnector's build_batch_spec function.

        Args:
            batch_definition (BatchDefinition): to be used to build batch_spec

        Returns:
            BatchSpec built from batch_definition
        """
        batch_spec: BatchSpec = super().build_batch_spec(
            batch_definition=batch_definition
        )
        return PathBatchSpec(batch_spec)

    # Interface Method
    def get_data_reference_count(self) -> int:
        """
        Returns the list of data_references known by this DataConnector from its _data_references_cache

        Returns:
            number of data_references known by this DataConnector.
        """
        total_references: int = len(self._data_references_cache)
        return total_references

    # Interface Method
    def get_unmatched_data_references(self) -> List[str]:
        """
        Returns the list of data_references unmatched by configuration by looping through items in
        _data_references_cache and returning data_references that do not have an associated data_asset.

        Returns:
            list of data_references that are not matched by configuration.
        """

        # noinspection PyTypeChecker
        unmatched_data_references: List[str] = list(
            dict(
                filter(
                    lambda element: element[1] is None,
                    self._data_references_cache.items(),
                )
            ).keys()
        )
        return unmatched_data_references

    # Interface Method
    def _generate_batch_spec_parameters_from_batch_definition(
        self, batch_definition: BatchDefinition
    ) -> dict:
        """
        This interface method examines "BatchDefinition" object and converts it to exactly one "data_reference" handle,
        based on partitioning behavior of given subclass (e.g., Regular Expressions for file path based DataConnector
        implementations).  Type of "data_reference" is storage dependent.  This method is then used to create storage
        system specific "BatchSpec" parameters for retrieving "Batch" of data.

        Args:
            batch_definition: input "BatchDefinition" object

        Returns:
            dict -- dictionary of "BatchSpec" properties
        """
        group_names: List[str] = self._regex_parser.get_all_group_names()
        path: str = map_batch_definition_to_data_reference_string_using_regex(
            batch_definition=batch_definition,
            regex_pattern=self._regex,
            group_names=group_names,
        )
        if not path:
            raise ValueError(
                f"""No data reference for data asset name "{batch_definition.data_asset_name}" matches the given
batch identifiers {batch_definition.batch_identifiers} from batch definition {batch_definition}.
"""
            )

        path = self._get_full_file_path(path=path)

        return {"path": path}

    def _refresh_data_references_cache(self) -> None:
        """
        This prototypical method populates cache, whose keys are data references and values are "BatchDefinition"
        objects.  Subsequently, "BatchDefinition" objects generated are amenable to flexible querying and sorting.

        It examines every "data_reference" handle and converts it to zero or more "BatchDefinition" objects, based on
        partitioning behavior of given subclass (e.g., Regular Expressions for file path based DataConnector
        implementations).  Type of each "data_reference" is storage dependent.
        """
        # Map data_references to batch_definitions
        self._data_references_cache = {}

        for data_reference in self.get_data_references():
            mapped_batch_definition_list: List[
                BatchDefinition
            ] | None = map_data_reference_string_to_batch_definition_list_using_regex(
                datasource_name=self.datasource_name,
                data_connector_name="experimental",
                data_asset_name=self.data_asset_name,
                data_reference=data_reference,
                regex_pattern=self._regex,
            )
            self._data_references_cache[data_reference] = mapped_batch_definition_list

        """
        This prototypical method examines "BatchDefinition" object and converts it to exactly one "data_reference"
        handle, based on partitioning behavior of given subclass (e.g., Regular Expressions for file path based
        DataConnector implementations).  Type of "data_reference" is storage dependent.  This method is then used to
        create storage system specific "BatchSpec" parameters for retrieving "Batch" of data.

        Args:
            batch_definition: input "BatchDefinition" object

        Returns:
            handle provided
        """

    # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
    # TODO: <Alex>ALEX</Alex>
    # def _sort_batch_definition_list(
    #     self, batch_definition_list: List[BatchDefinition]
    # ) -> List[BatchDefinition]:
    #     """
    #     Use configured sorters to sort batch_definition
    #
    #     Args:
    #         batch_definition_list (list): list of batch_definitions to sort
    #
    #     Returns:
    #         sorted list of batch_definitions
    #
    #     """
    #     sorters: Iterator[Sorter] = reversed(list(self.sorters.values()))
    #     for sorter in sorters:
    #         batch_definition_list = sorter.get_sorted_batch_definitions(
    #             batch_definitions=batch_definition_list
    #         )
    #
    #     return batch_definition_list
    # TODO: <Alex>ALEX</Alex>

    def _get_batch_definition_list_from_cache(self) -> List[BatchDefinition]:
        batch_definition_list: List[BatchDefinition] = [
            batch_definitions[0]
            for batch_definitions in self._data_references_cache.values()
            if batch_definitions is not None
        ]
        return batch_definition_list

    @abstractmethod
    def _get_full_file_path(self, path: str) -> str:
        pass