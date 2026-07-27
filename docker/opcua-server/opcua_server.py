import asyncio
import logging
import random

from asyncua import Server, ua

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("opcua-server")

ENDPOINT = "opc.tcp://0.0.0.0:4840/iiot/compressors/"
NAMESPACE_URI = "http://iiot.local/compressors"

COMPRESSOR_IDS = ["compressor-1", "compressor-2", "compressor-3", "compressor-4", "compressor-5"]

TAG_SPECS = {
    "vibration_mm_s": {"baseline": 2.0, "noise": 0.15, "anomaly_delta": 6.0},
    "temperature_c": {"baseline": 75.0, "noise": 1.0, "anomaly_delta": 30.0},
    "pressure_bar": {"baseline": 7.5, "noise": 0.2, "anomaly_delta": -3.0},
    "current_amps": {"baseline": 40.0, "noise": 1.5, "anomaly_delta": 15.0},
}

SAMPLE_INTERVAL_SEC = 1.0
ANOMALY_CHECK_INTERVAL_SEC = 10.0
ANOMALY_PROBABILITY_PER_CHECK = 0.004
ANOMALY_DURATION_SEC = 20.0


class CompressorSimState:
    def __init__(self, compressor_id):
        self.compressor_id = compressor_id
        self.anomaly_tag = None
        self.anomaly_ends_at = None

    def maybe_trigger_anomaly(self, now):
        if self.anomaly_tag is not None:
            return
        if random.random() < ANOMALY_PROBABILITY_PER_CHECK:
            self.anomaly_tag = random.choice(list(TAG_SPECS.keys()))
            self.anomaly_ends_at = now + ANOMALY_DURATION_SEC
            logger.info(
                "%s entering anomaly on %s for %.0fs",
                self.compressor_id, self.anomaly_tag, ANOMALY_DURATION_SEC,
            )

    def clear_if_expired(self, now):
        if self.anomaly_tag is not None and now >= self.anomaly_ends_at:
            logger.info("%s anomaly on %s cleared", self.compressor_id, self.anomaly_tag)
            self.anomaly_tag = None
            self.anomaly_ends_at = None

    def read_value(self, tag_name):
        spec = TAG_SPECS[tag_name]
        value = spec["baseline"] + random.gauss(0, spec["noise"])
        if self.anomaly_tag == tag_name:
            value += spec["anomaly_delta"] + random.gauss(0, spec["noise"] * 2)
        return round(value, 3)


async def build_address_space(server, idx):
    objects = server.get_objects_node()
    states = {}
    tag_nodes = {}

    for compressor_id in COMPRESSOR_IDS:
        compressor_obj = await objects.add_object(idx, compressor_id)
        states[compressor_id] = CompressorSimState(compressor_id)
        tag_nodes[compressor_id] = {}
        for tag_name, spec in TAG_SPECS.items():
            var = await compressor_obj.add_variable(idx, tag_name, spec["baseline"])
            await var.set_writable(False)
            tag_nodes[compressor_id][tag_name] = var

    return states, tag_nodes


async def simulation_loop(states, tag_nodes):
    last_anomaly_check = 0.0
    loop_start = asyncio.get_event_loop().time()

    while True:
        now = asyncio.get_event_loop().time() - loop_start

        if now - last_anomaly_check >= ANOMALY_CHECK_INTERVAL_SEC:
            for state in states.values():
                state.clear_if_expired(now)
                state.maybe_trigger_anomaly(now)
            last_anomaly_check = now

        for compressor_id, state in states.items():
            for tag_name, var in tag_nodes[compressor_id].items():
                value = state.read_value(tag_name)
                await var.write_value(ua.Variant(value, ua.VariantType.Double))

        await asyncio.sleep(SAMPLE_INTERVAL_SEC)


async def main():
    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    server.set_server_name("IIoT Compressor Fleet Simulator")

    idx = await server.register_namespace(NAMESPACE_URI)
    states, tag_nodes = await build_address_space(server, idx)

    logger.info("OPC-UA server starting at %s", ENDPOINT)
    async with server:
        await simulation_loop(states, tag_nodes)


if __name__ == "__main__":
    asyncio.run(main())
