from typing import Callable, List, Tuple, Union

from avro.schema import Field, RecordSchema

from datahub.metadata.schema_classes import DictWrapper
from datahub.utilities.urns.dataset_urn import DatasetUrn
from datahub.utilities.urns.urn import Urn, guess_entity_type

_Path = List[Union[str, int]]


def list_urns_with_path(model: DictWrapper) -> List[Tuple[str, _Path]]:
    """List urns in the given model with their paths.

    Args:
        model: The model to list urns from.

    Returns:
        A list of tuples of the form (urn, path), where path is a list of keys.
    """

    schema: RecordSchema = model.RECORD_SCHEMA

    urns: List[Tuple[str, _Path]] = []

    for key, value in model.items():
        if not value:
            continue

        field_schema: Field = schema.fields_dict[key]
        is_urn = field_schema.get_prop("Urn") is not None

        if isinstance(value, DictWrapper):
            for urn, path in list_urns_with_path(value):
                urns.append((urn, [key, *path]))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, DictWrapper):
                    for urn, path in list_urns_with_path(item):
                        urns.append((urn, [key, i, *path]))
                elif is_urn:
                    urns.append((item, [key, i]))
        elif is_urn:
            urns.append((value, [key]))

    return urns


def transform_urns(model: DictWrapper, func: Callable[[str], str]) -> None:
    """
    Rewrites all URNs in the given object according to the given function.
    """

    for old_urn, path in list_urns_with_path(model):
        new_urn = func(old_urn)
        if old_urn != new_urn:
            _modify_at_path(model, path, new_urn)


def _modify_at_path(
    model: Union[DictWrapper, list], path: _Path, new_value: str
) -> None:
    assert len(path) > 0

    if len(path) == 1:
        if isinstance(path[0], int):
            assert isinstance(model, list)
            model[path[0]] = new_value
        else:
            assert isinstance(model, DictWrapper)
            model._inner_dict[path[0]] = new_value
    elif isinstance(path[0], int):
        assert isinstance(model, list)
        return _modify_at_path(model[path[0]], path[1:], new_value)
    else:
        assert isinstance(model, DictWrapper)
        return _modify_at_path(model._inner_dict[path[0]], path[1:], new_value)


def _lowercase_dataset_urn(dataset_urn: str) -> str:
    cur_urn = DatasetUrn.create_from_string(dataset_urn)
    cur_urn._entity_id[1] = cur_urn._entity_id[1].lower()
    return str(cur_urn)


def lowercase_dataset_urns(model: DictWrapper) -> None:
    def modify_urn(urn: str) -> str:
        if guess_entity_type(urn) == "dataset":
            return _lowercase_dataset_urn(urn)
        elif guess_entity_type(urn) == "schemaField":
            cur_urn = Urn.create_from_string(urn)
            cur_urn._entity_id[0] = _lowercase_dataset_urn(cur_urn._entity_id[0])
            return str(cur_urn)
        return urn

    transform_urns(model, modify_urn)
