from monty.json import MSONable
from dataclasses import dataclass
from pydantic import BaseModel, PositiveInt, confloat, constr, validator
from typing import List, Optional, Union
from pathlib import Path
import pymatgen
import openff.toolkit as tk

from pymatgen.io.openmm.utils import xyz_to_molecule
from pymatgen.analysis.graphs import MoleculeGraph

import numpy as np


class Geometry(BaseModel):
    """
    A geometry schema to be used for input to OpenMMSolutionGen.
    """

    xyz: Union[pymatgen.core.Molecule, str, Path]

    @validator("xyz")
    def xyz_is_valid(cls, xyz):
        """check that xyz generates a valid molecule"""
        try:
            xyz_to_molecule(xyz)
        except Exception:
            raise ValueError(f"Invalid xyz file or molecule: {xyz}")
        return xyz_to_molecule(xyz)


class InputMoleculeSpec(BaseModel):
    """
    A molecule schema to be used for input to OpenMMSolutionGen.
    """

    smile: str
    count: int
    name: Optional[str] = None
    charge_scaling: Optional[confloat(ge=0.1, le=10)] = 1.0  # type: ignore
    force_field: Optional[constr(to_lower=True)] = None  # type: ignore
    geometries: Optional[List[Geometry]] = None
    partial_charges: Optional[List[float]] = None
    partial_charge_label: Optional[str] = None
    max_conformers: PositiveInt = 1

    class Config:
        # needed to allow for np.ndarray
        arbitrary_types_allowed = True

    @validator("smile")
    def smile_is_valid(cls, smile):
        """check that smile generates a valid molecule"""
        try:
            tk.Molecule.from_smiles(smile)
        except Exception:
            raise ValueError(f"Invalid SMILES string: {smile}")
        return smile

    @validator("force_field", pre=True)
    def lower_case_ff(cls, force_field):
        """check that force_field is valid"""
        return force_field.lower()

    @validator("name", always=True)
    def set_name(cls, name, values):
        """assign name if not provided"""
        if name is None:
            return values["smile"]
        return name

    @validator("geometries", pre=True)
    def convert_xyz_to_geometry(cls, geometries, values):
        """convert xyz to Geometry"""
        if geometries is not None:
            geometries = [Geometry(xyz=xyz) for xyz in geometries]
            # assert xyz lengths are the same
            n_atoms = tk.Molecule.from_smiles(values["smile"]).n_atoms
            if not all([len(geometry.xyz) == n_atoms for geometry in geometries]):
                raise ValueError(
                    "All geometries must have the same number of atoms as the molecule"
                    " defined in the SMILES string."
                )
            return geometries
        return geometries

    @validator("partial_charges", pre=True)
    def check_geometry_is_set(cls, partial_charges, values):
        """check that geometries is set if partial_charges is set"""
        if partial_charges is not None:
            geometries = values.get("geometries")
            if geometries is None:
                raise ValueError("geometries must be set if partial_charges is set")
            if not len(partial_charges) == len(geometries[0].xyz):
                raise ValueError(
                    "partial_charges must be the same length as all geometries"
                )
        return list(partial_charges)

    @validator("partial_charge_label", pre=True)
    def check_partial_charges_are_set(cls, partial_charge_label, values):
        """label partial charge method if partial_charges is set, defaults to 'custom'"""
        if partial_charge_label is not None:
            if values.get("partial_charges") is None:
                raise ValueError(
                    "partial_charges must be set if partial_charge_label is set"
                )
            return partial_charge_label
        else:
            if values.get("partial_charges") is None:
                return None
            return "custom"


class InputSetSettings(BaseModel):
    # TODO: need to fill this out and integrate with SolutionGen and InputSet
    # one option would be to have base settings and then inherit from multiple classes
    settings: dict


@dataclass
class MoleculeSpec(MSONable):
    name: str
    count: int
    smile: str
    force_field: str
    formal_charge: int
    charge_method: str
    molgraph: MoleculeGraph


@dataclass
class SetContents(MSONable):
    molecule_specs: List[MoleculeSpec]
    force_fields: List[str]
    partial_charge_methods: List[str]
    atom_types: np.ndarray[int]
    atom_resnames: np.ndarray[int]
