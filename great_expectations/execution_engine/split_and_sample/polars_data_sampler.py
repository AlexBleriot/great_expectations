import hashlib
import random  # noqa: F401

try:
    from polars import DataFrame as pl_DataFrame

except ImportError:
    pl_DataFrame = None

import great_expectations.exceptions as ge_exceptions
from great_expectations.core.id_dict import BatchSpec  # noqa: TCH001
from great_expectations.execution_engine.split_and_sample.data_sampler import (
    DataSampler,
)


class PolarsDataSampler(DataSampler):
    """Methods for sampling a polars dataframe."""

    def sample_using_limit(
        self, df: pl_DataFrame, batch_spec: BatchSpec
    ) -> pl_DataFrame:
        """Sample the first n rows of data.

        Args:
            df: polars dataframe.
            batch_spec: Should contain key `n` in sampling_kwargs, the number of
                values in the sample e.g. sampling_kwargs={"n": 100}.

        Returns:
            Sampled dataframe

        Raises:
            SamplerError
        """
        self.verify_batch_spec_sampling_kwargs_exists(batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("n", batch_spec)

        n: int = batch_spec["sampling_kwargs"]["n"]
        return df.head(n)

    def sample_using_random(
        self,
        df: pl_DataFrame,
        batch_spec: BatchSpec,
    ) -> pl_DataFrame:
        """Take a random sample of rows, retaining proportion p.

        Args:
            df: dataframe to sample
            batch_spec: Can contain key `p` (float) which defaults to 0.1
                if not provided.

        Returns:
            Sampled dataframe

        Raises:
            SamplerError
        """
        p = self.get_sampling_kwargs_value_or_default(
            batch_spec=batch_spec, sampling_kwargs_key="p", default_value=0.1
        )

        return df.sample(frac=p)

    def sample_using_mod(
        self,
        df: pl_DataFrame,
        batch_spec: BatchSpec,
    ) -> pl_DataFrame:
        """Take the mod of named column, and only keep rows that match the given value.

        Args:
            df: dataframe to sample
            batch_spec: should contain keys `column_name`, `mod` and `value`

        Returns:
            Sampled dataframe

        Raises:
            SamplerError
        """
        self.verify_batch_spec_sampling_kwargs_exists(batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("column_name", batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("mod", batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("value", batch_spec)
        column_name = self.get_sampling_kwargs_value_or_default(
            batch_spec, "column_name"
        )
        mod = self.get_sampling_kwargs_value_or_default(batch_spec, "mod")
        value = self.get_sampling_kwargs_value_or_default(batch_spec, "value")

        return df[df[column_name].apply(lambda x: x % mod == value)]

    def sample_using_a_list(
        self,
        df: pl_DataFrame,
        batch_spec: BatchSpec,
    ) -> pl_DataFrame:
        """Match the values in the named column against value_list, and only keep the matches.

        Args:
            df: dataframe to sample
            batch_spec: should contain keys `column_name` and `value_list`

        Returns:
            Sampled dataframe

        Raises:
            SamplerError
        """
        self.verify_batch_spec_sampling_kwargs_exists(batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("column_name", batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("value_list", batch_spec)

        column_name = self.get_sampling_kwargs_value_or_default(
            batch_spec, "column_name"
        )
        value_list = self.get_sampling_kwargs_value_or_default(batch_spec, "value_list")

        return df[df[column_name].is_in(value_list)]

    def sample_using_hash(
        self,
        df: pl_DataFrame,
        batch_spec: BatchSpec,
    ) -> pl_DataFrame:
        """Hash the values in the named column, and only keep rows that match the given hash_value.

        Args:
            df: dataframe to sample
            batch_spec: should contain keys `column_name` and optionally `hash_digits`
                (default is 1 if not provided), `hash_value` (default is "f" if not provided),
                and `hash_function_name` (default is "md5" if not provided)

        Returns:
            Sampled dataframe

        Raises:
            SamplerError
        """
        self.verify_batch_spec_sampling_kwargs_exists(batch_spec)
        self.verify_batch_spec_sampling_kwargs_key_exists("column_name", batch_spec)
        column_name = self.get_sampling_kwargs_value_or_default(
            batch_spec, "column_name"
        )
        hash_digits: int = self.get_sampling_kwargs_value_or_default(
            batch_spec=batch_spec, sampling_kwargs_key="hash_digits", default_value=1
        )
        hash_value = self.get_sampling_kwargs_value_or_default(
            batch_spec=batch_spec, sampling_kwargs_key="hash_value", default_value="f"
        )

        hash_function_name: str = self.get_sampling_kwargs_value_or_default(
            batch_spec=batch_spec,
            sampling_kwargs_key="hash_function_name",
            default_value="md5",
        )

        try:
            hash_func = getattr(hashlib, hash_function_name)
        except (TypeError, AttributeError):
            raise (
                ge_exceptions.ExecutionEngineError(
                    f"""The sampling method used with PolarsExecutionEngine has a reference to an invalid hash_function_name.
                       Reference to {hash_function_name} cannot be found."""
                )
            )

        matches = df[column_name].apply(
            lambda x: hash_func(str(x).encode()).hexdigest()[-1 * hash_digits :]
            == hash_value
        )
        return df[matches]
