# Copyright The Caikit Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
This file contains our logic about what constitutes a proto-able for RPC generation purposes
"""

# Standard
from typing import Dict, Type, Union, get_args, get_origin
import typing

# First Party
import alog

# Local
from caikit.core.data_model.dataobject import DATAOBJECT_PY_TO_PROTO_TYPES
from caikit.runtime.service_generation.type_helpers import is_data_model_type

log = alog.use_channel("PROTOABLES")


def to_protoable_signature(signature: Dict[str, Type]) -> Dict[str, Type]:
    """Returns dictionary of protoable types only
    If there is a Union, pick the protoable type

    Args:
        signature: Dict[str, Type]
            module signature of parameters and types
    """
    protoables = {}
    log.debug("Building protoable signature for %s", signature)
    for arg, arg_type in signature.items():
        protoable_type = handle_protoables_in_union(arg_type)
        if protoable_type:
            protoables[arg] = protoable_type

    return protoables


def handle_protoables_in_union(arg_type: Type) -> Type:
    """Handles various protoable arg types from a Union.

    If arg_type is a union, then this will return the union back if all types in it are proto-able,
    or the first proto-able arg type if the union has non-protoable arg types.

    If arg_type is not a union nor protoable at all, this returns None.

    Examples:
    Union[protoable_type, non_protoable_type] -> protoable_type
    Union[protoable_type_1, protoable_type_2] -> Union[protoable_type_1, protoable_type_2]
    Union[protoable_type_1, protoable_type_2, non_protoable_type] -> protoable_type_1
    """
    if is_protoable_type(arg_type):
        if typing.get_origin(arg_type) == Union:
            union_protoables = [
                union_val
                for union_val in typing.get_args(arg_type)
                if is_protoable_type(union_val)
            ]
            # if all are protoable, return the union (which will create a oneof)
            if len(union_protoables) == len(typing.get_args(arg_type)):
                return arg_type
            # if there's only 1 protoable found, return that
            if len(union_protoables) == 1:
                return union_protoables[0]
            # otherwise, try to get the data model objects in the Union
            dm_types = [arg for arg in union_protoables if is_data_model_type(arg)]
            # if there are multiple, pick the first one
            if len(dm_types) > 0:
                log.debug2(
                    "Picking first data model type %s in union protoables %s",
                    dm_types,
                    union_protoables,
                )
                return dm_types[0]
            log.debug(
                "Just picking first protoable type %s in union",
                union_protoables[0],
            )
            return union_protoables[0]
        return arg_type
    log.debug("Skipping non-protoable argument type [%s]", arg_type)


def extract_data_model_type_from_union(arg_type: Type) -> Type:
    """Helper function that determines the right data model type to use from a Union"""

    # Decompose this type using typing to determine if it's a useful typing hint
    typing_origin = get_origin(arg_type)
    typing_args = get_args(arg_type)

    # If this is a data model type, no need to do anything
    if is_data_model_type(arg_type):
        return arg_type

    # Handle Unions by looking for a data model object in the union
    if typing_origin is Union:
        dm_types = [arg for arg in typing_args if is_data_model_type(arg)]
        if dm_types:
            log.debug2(
                "Found data model types in Union: [%s], taking first one", dm_types
            )
            return extract_data_model_type_from_union(dm_types[0])

    # if it's anything else we just return as is
    # we don't actually want to throw errors from service generation
    log.warning("Return type [%s] not a DM type, returning as is", arg_type)
    return arg_type


def is_protoable_type(arg_type: Type) -> bool:
    """
    Returns True if arg_type is in PROTO_TYPE_MAP(float, int, bool, str, bytes)
    Or if it's an imported Caikit data model class.
    Or if it's a Union of at least one of those.
    Or if it's a List of one of those.
    False otherwise"""
    proto_primitive_set = list(DATAOBJECT_PY_TO_PROTO_TYPES.keys())

    if arg_type in proto_primitive_set:
        return True
    if is_data_model_type(arg_type):
        return True

    if typing.get_origin(arg_type) == list:
        log.debug2("Arg is List")
        if len(typing.get_args(arg_type)) == 0:
            log.debug2("List annotation has no type")
            return False
        return typing.get_args(arg_type)[0] in proto_primitive_set

    if typing.get_origin(arg_type) == Union:
        log.debug2("Arg is Union")
        # pylint: disable=use-a-generator
        return any([is_protoable_type(arg) for arg in typing.get_args(arg_type)])

    log.debug2("Arg is not protoable, arg_type: %s", arg_type)
    return False
