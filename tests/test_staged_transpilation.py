"""Regression checks for the staged center-out routing boundary."""

import unittest

from qiskit import QuantumCircuit

from p9solver.pipeline import rewire_layers
from p9solver.qiskit_utils import iter_layers


class StagedTranspilationTest(unittest.TestCase):
    def test_rewire_preserves_existing_measurement_frame(self):
        """The deferred outer routing must retain the original classical bits."""
        circuit = QuantumCircuit(4, 4)
        circuit.cx(0, 3)
        circuit.cx(1, 2)
        circuit.measure_all(add_bits=False)

        routed = rewire_layers(
            list(iter_layers(circuit)), [0, 1, 2, 3], seed=123, sabre_trials=2
        )
        classical_indices = [
            layer.find_bit(instruction.clbits[0]).index
            for layer in routed
            for instruction in layer.data
            if instruction.operation.name == "measure"
        ]

        self.assertEqual(sorted(classical_indices), [0, 1, 2, 3])
