from typing import Union

import dagster as dg
import pytest
from dagster import IOManagerDefinition


def make_io_manager(
    asset: Union[dg.SourceAsset, dg.AssetSpec], input_value=5, expected_metadata={}
):
    class MyIOManager(dg.IOManager):
        def handle_output(self, context, obj): ...

        def load_input(self, context):
            self.loaded_input = True
            assert context.asset_key == asset.key
            for key, value in expected_metadata.items():
                assert context.upstream_output.definition_metadata[key] == value  # pyright: ignore[reportOptionalMemberAccess]
            return input_value

    return MyIOManager()


def test_source_asset_input_value():
    asset1 = dg.SourceAsset("asset1", metadata={"foo": "bar"})

    @dg.op
    def op1(input1):
        assert input1 == 5

    @dg.graph
    def graph1():
        op1(asset1)

    io_manager = make_io_manager(asset1, expected_metadata={"foo": "bar"})
    assert graph1.execute_in_process(resources={"io_manager": io_manager}).success
    assert io_manager.loaded_input


def test_external_asset_input_value():
    asset1 = dg.AssetSpec("asset1", metadata={"foo": "bar"})

    @dg.op
    def op1(input1):
        assert input1 == 5

    @dg.graph
    def graph1():
        op1(asset1)

    io_manager = make_io_manager(asset1, expected_metadata={"foo": "bar"})
    assert graph1.execute_in_process(resources={"io_manager": io_manager}).success
    assert io_manager.loaded_input


def test_one_input_source_asset_other_input_upstream_op():
    asset1 = dg.SourceAsset("asset1", io_manager_key="a")

    @dg.op
    def op1():
        return 7

    @dg.op
    def op2(input1, input2):
        assert input1 == 5
        assert input2 == 7

    @dg.graph
    def graph1():
        op2(asset1, op1())

    io_manager = make_io_manager(asset1)
    assert graph1.execute_in_process(resources={"a": io_manager}).success
    assert io_manager.loaded_input


def test_partitioned_source_asset_input_value():
    partitions_def = dg.StaticPartitionsDefinition(["foo", "bar"])
    asset1 = dg.SourceAsset("asset1", partitions_def=partitions_def)

    class MyIOManager(dg.IOManager):
        def handle_output(self, context, obj): ...

        def load_input(self, context):
            self.loaded_input = True
            assert context.asset_key == asset1.key
            assert context.partition_key == "foo"
            return 5

    @dg.op
    def op1(input1):
        assert input1 == 5

    io_manager = MyIOManager()

    @dg.job(
        partitions_def=partitions_def,
        resource_defs={"io_manager": IOManagerDefinition.hardcoded_io_manager(io_manager)},
    )
    def job1():
        op1(asset1)

    assert job1.execute_in_process(partition_key="foo").success
    assert io_manager.loaded_input


def test_non_partitioned_job_partitioned_source_asset():
    partitions_def = dg.StaticPartitionsDefinition(["foo", "bar"])
    asset1 = dg.SourceAsset("asset1", partitions_def=partitions_def)

    class MyIOManager(dg.IOManager):
        def handle_output(self, context, obj): ...

        def load_input(self, context):
            self.loaded_input = True
            assert context.asset_key == asset1.key
            assert set(context.asset_partition_keys) == {"foo", "bar"}
            return 5

    @dg.op
    def op1(input1):
        assert input1 == 5

    io_manager = MyIOManager()

    @dg.job(resource_defs={"io_manager": IOManagerDefinition.hardcoded_io_manager(io_manager)})
    def job1():
        op1(asset1)

    assert job1.execute_in_process().success
    assert io_manager.loaded_input


def test_multiple_source_asset_inputs():
    asset1 = dg.SourceAsset("asset1", io_manager_key="iomanager1")
    asset2 = dg.SourceAsset("asset2", io_manager_key="iomanager2")

    @dg.op
    def op1(input1, input2):
        assert input1 == 5
        assert input2 == 7

    @dg.graph
    def graph1():
        op1(asset1, asset2)

    iomanager1 = make_io_manager(asset1, 5)
    iomanager2 = make_io_manager(asset2, 7)
    assert graph1.execute_in_process(
        resources={"iomanager1": iomanager1, "iomanager2": iomanager2}
    ).success
    assert iomanager1.loaded_input


def test_two_inputs_same_source_asset():
    asset1 = dg.SourceAsset("asset1")

    @dg.op
    def op1(input1):
        assert input1 == 5

    @dg.op
    def op2(input2):
        assert input2 == 5

    @dg.graph
    def graph1():
        op1(asset1)
        op2(asset1)

    io_manager = make_io_manager(asset1)
    assert graph1.execute_in_process(resources={"io_manager": io_manager}).success
    assert io_manager.loaded_input


def test_nested_source_asset_input_value():
    asset1 = dg.SourceAsset("asset1")

    @dg.op
    def op1(input1):
        assert input1 == 5

    @dg.graph
    def inner_graph():
        op1(asset1)

    @dg.graph
    def outer_graph():
        inner_graph()

    io_manager = make_io_manager(asset1)
    assert outer_graph.execute_in_process(resources={"io_manager": io_manager}).success
    assert io_manager.loaded_input


def test_nested_input_mapped_source_asset_input_value():
    asset1 = dg.SourceAsset("asset1")

    @dg.op
    def op1(input1):
        assert input1 == 5

    @dg.graph
    def inner_graph(inputx):
        op1(inputx)

    @dg.graph
    def outer_graph():
        inner_graph(asset1)

    io_manager = make_io_manager(asset1)
    assert outer_graph.execute_in_process(resources={"io_manager": io_manager}).success
    assert io_manager.loaded_input


def test_source_assets_list_input_value():
    asset1 = dg.SourceAsset("asset1")
    asset2 = dg.SourceAsset("asset2")

    @dg.op
    def op1(input1):
        assert input1 == [dg.AssetKey("asset1"), dg.AssetKey("asset2")]

    # not yet supported
    with pytest.raises(
        dg.DagsterInvalidDefinitionError,
        match="Lists can only contain the output from previous op invocations or input mappings",
    ):

        @dg.graph
        def graph1():
            op1([asset1, asset2])
