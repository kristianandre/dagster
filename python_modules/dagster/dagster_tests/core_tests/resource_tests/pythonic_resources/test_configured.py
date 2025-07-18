from typing import Any

import dagster as dg
import pytest
from dagster import ConfigurableResource, InitResourceContext
from dagster._check import CheckError


def test_config_mapping_return_resource_config_dict_noargs() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    @dg.configured(MyResource)
    def my_resource_noargs(_) -> dict[str, Any]:
        return {"resource_param": "foo"}

    @dg.op
    def do_something(my_resource: ConfigurableResource) -> str:
        return my_resource.resource_param

    @dg.job
    def do_it_all() -> None:
        do_something()

    result = do_it_all.execute_in_process(resources={"my_resource": my_resource_noargs})
    assert result.success
    assert result.output_for_node("do_something") == "foo"


def test_config_mapping_return_resource_config_dict() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    @dg.resource(config_schema={"resource_param": str})
    def my_resource_legacy(context: InitResourceContext) -> MyResource:
        return MyResource(resource_param=context.resource_config["resource_param"])

    @dg.configured(my_resource_legacy, config_schema={"simplified_param": str})
    def my_resource_legacy_simplified(config_in) -> dict[str, Any]:
        return {"resource_param": config_in["simplified_param"]}

    @dg.op
    def do_something(my_resource: ConfigurableResource) -> str:
        return my_resource.resource_param

    @dg.job
    def do_it_all() -> None:
        do_something()

    result = do_it_all.execute_in_process(
        resources={
            "my_resource": my_resource_legacy_simplified.configured({"simplified_param": "foo"})
        }
    )
    assert result.success
    assert result.output_for_node("do_something") == "foo"

    class MyResourceSimplifiedConfig(dg.Config):
        simplified_param: str

    # New, fancy config mapping takes in a Pythonic config object but returns normal config dict
    @dg.configured(MyResource)
    def my_resource_simplified(config_in: MyResourceSimplifiedConfig) -> dict[str, Any]:
        return {"resource_param": config_in.simplified_param}

    result = do_it_all.execute_in_process(
        resources={"my_resource": my_resource_simplified.configured({"simplified_param": "foo"})}
    )
    assert result.success
    assert result.output_for_node("do_something") == "foo"


def test_config_mapping_return_resource_object() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    @dg.op
    def do_something(my_resource: ConfigurableResource) -> str:
        return my_resource.resource_param

    @dg.job
    def do_it_all() -> None:
        do_something()

    class MyResourceSimplifiedConfig(dg.Config):
        simplified_param: str

    # New, fancy config mapping takes in a Pythonic config object and returns a constructed resource
    @dg.configured(MyResource)
    def my_resource_simplified(config_in: MyResourceSimplifiedConfig) -> MyResource:
        return MyResource(resource_param=config_in.simplified_param)

    result = do_it_all.execute_in_process(
        resources={"my_resource": my_resource_simplified.configured({"simplified_param": "foo"})}
    )
    assert result.success
    assert result.output_for_node("do_something") == "foo"


def test_config_annotation_no_config_schema_err() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    class MyResourceSimplifiedConfig(dg.Config):
        simplified_param: str

    # Ensure that we error if we try to provide a config_schema to a @configured function
    # which has a Config-annotated param - no need to provide a config_schema in this case
    with pytest.raises(
        CheckError,
        match="Cannot provide config_schema to @configured function with Config-annotated param",
    ):

        @dg.configured(MyResource, config_schema={"simplified_param": str})
        def my_resource_simplified(config_in: MyResourceSimplifiedConfig): ...


def test_config_annotation_extra_param_err() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    class MyResourceSimplifiedConfig(dg.Config):
        simplified_param: str

    # Ensure that we error if the @configured function has an extra param
    with pytest.raises(
        CheckError,
        match="@configured function should have exactly one parameter",
    ):

        @dg.configured(MyResource)
        def my_resource_simplified(config_in: MyResourceSimplifiedConfig, useless_param: str): ...


def test_factory_resource_pattern_noargs() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    class MyResourceNoargs(dg.ConfigurableResource):
        def create_resource(self, context: InitResourceContext) -> Any:
            return MyResource(resource_param="foo")

    @dg.op
    def do_something(my_resource: ConfigurableResource) -> str:
        return my_resource.resource_param

    @dg.job
    def do_it_all() -> None:
        do_something()

    result = do_it_all.execute_in_process(resources={"my_resource": MyResourceNoargs()})
    assert result.success
    assert result.output_for_node("do_something") == "foo"


def test_factory_resource_pattern_args() -> None:
    class MyResource(dg.ConfigurableResource):
        resource_param: str

    class MyResourceFromInt(dg.ConfigurableResource):
        an_int: int

        def create_resource(self, context: InitResourceContext) -> Any:
            return MyResource(resource_param=str(self.an_int))

    @dg.op
    def do_something(my_resource: ConfigurableResource) -> str:
        return my_resource.resource_param

    @dg.job
    def do_it_all() -> None:
        do_something()

    result = do_it_all.execute_in_process(resources={"my_resource": MyResourceFromInt(an_int=10)})
    assert result.success
    assert result.output_for_node("do_something") == "10"
