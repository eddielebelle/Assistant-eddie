"""Smart home MQTT bridge for Eddie."""

import logging

from eddie.mqtt.client import get_mqtt_client

logger = logging.getLogger(__name__)


def control_device(device: str, action: str) -> str:
    """Control a smart home device via MQTT.

    Publishes a command to the device's MQTT topic.
    """
    topic = f"eddie/devices/{device.lower().replace(' ', '_')}/set"
    payload = action

    try:
        client = get_mqtt_client()
        client.publish(topic, payload)
        logger.info("Published to %s: %s", topic, payload)
        return f"Sent '{action}' command to {device}."
    except Exception:
        logger.exception("Failed to control device '%s'", device)
        return f"Failed to send command to {device}."
