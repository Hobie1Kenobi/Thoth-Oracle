"""
IBM Quantum Backend Manager
Manages connections to IBM Quantum hardware and provides backend selection
for the trading agents.
"""

import os
import logging
from typing import Optional
from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator

logger = logging.getLogger(__name__)

_service = None
_backend = None

def get_ibm_service():
    """Get or create a QiskitRuntimeService connection."""
    global _service
    if _service is not None:
        return _service

    token = os.getenv("IBMQ_API_TOKEN")
    crn = os.getenv("IBM_QUANTUM_CRN")

    if not token or token == "your-ibm-quantum-token":
        logger.info("No IBM Quantum API token configured, using local simulator")
        return None

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        if crn:
            _service = QiskitRuntimeService(
                channel="ibm_cloud", token=token, instance=crn
            )
        else:
            _service = QiskitRuntimeService(
                channel="ibm_quantum", token=token
            )
        logger.info("Connected to IBM Quantum")
        return _service
    except Exception as e:
        logger.warning(f"Failed to connect to IBM Quantum: {e}")
        return None


def get_backend(prefer_hardware: bool = True, backend_name: Optional[str] = None):
    """Get the best available quantum backend.

    Args:
        prefer_hardware: If True, prefer real hardware over simulator.
        backend_name: Specific backend name to request.

    Returns:
        A quantum backend (IBM hardware or AerSimulator).
    """
    global _backend

    if not prefer_hardware:
        return AerSimulator()

    service = get_ibm_service()
    if service is None:
        return AerSimulator()

    try:
        if backend_name:
            _backend = service.backend(backend_name)
        else:
            _backend = service.least_busy(operational=True)
        name = _backend.configuration().backend_name
        qubits = _backend.configuration().n_qubits
        logger.info(f"Using IBM Quantum backend: {name} ({qubits} qubits)")
        return _backend
    except Exception as e:
        logger.warning(f"Could not get IBM backend, falling back to simulator: {e}")
        return AerSimulator()


def run_on_hardware(circuit: QuantumCircuit, backend=None, shots: int = 4000):
    """Run a circuit on IBM Quantum hardware using SamplerV2.

    Args:
        circuit: The quantum circuit to run.
        backend: Backend to use. If None, uses get_backend().
        shots: Number of shots.

    Returns:
        dict mapping bitstring -> count
    """
    if backend is None:
        backend = get_backend(prefer_hardware=True)

    is_ibm = hasattr(backend, 'configuration') and not isinstance(backend, AerSimulator)

    if is_ibm:
        return _run_ibm_sampler(circuit, backend, shots)
    else:
        return _run_aer(circuit, backend, shots)


def _run_aer(circuit, backend, shots):
    """Run on local AerSimulator."""
    result = backend.run(circuit, shots=shots).result()
    return result.get_counts()


def _run_ibm_sampler(circuit, backend, shots):
    """Run on IBM Quantum hardware via SamplerV2."""
    from qiskit_ibm_runtime import SamplerV2

    pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
    transpiled = pm.run(circuit)

    sampler = SamplerV2(mode=backend)
    job = sampler.run([transpiled], shots=shots)
    logger.info(f"IBM Quantum job submitted: {job.job_id()}")

    result = job.result()
    pub_result = result[0]

    data_bin = pub_result.data
    creg_names = list(data_bin.keys()) if hasattr(data_bin, 'keys') else dir(data_bin)
    for name in ['meas', 'c', 'c0']:
        if hasattr(data_bin, name):
            return getattr(data_bin, name).get_counts()

    for attr in dir(data_bin):
        if not attr.startswith('_'):
            obj = getattr(data_bin, attr)
            if hasattr(obj, 'get_counts'):
                return obj.get_counts()

    raise RuntimeError(f"Could not extract counts from result. Data attributes: {[a for a in dir(data_bin) if not a.startswith('_')]}")


def list_backends():
    """List all available IBM Quantum backends."""
    service = get_ibm_service()
    if service is None:
        return [{"name": "aer_simulator", "qubits": 32, "simulator": True, "pending": 0}]

    backends = []
    for b in service.backends():
        config = b.configuration()
        status = b.status()
        backends.append({
            "name": config.backend_name,
            "qubits": config.n_qubits,
            "simulator": config.simulator,
            "pending": status.pending_jobs,
            "operational": status.operational,
        })
    return backends
