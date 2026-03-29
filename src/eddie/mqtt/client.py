"""Shared MQTT client for Eddie IoT integration."""

import logging

import paho.mqtt.client as mqtt

from eddie.config import get_config

logger = logging.getLogger(__name__)

_client: mqtt.Client | None = None


def get_mqtt_client() -> mqtt.Client:
    """Get or create a shared MQTT client."""
    global _client
    if _client is None:
        config = get_config()
        _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "eddie")
        _client.username_pw_set(config.mqtt_username, config.mqtt_password)
        _client.on_connect = _on_connect
        _client.on_disconnect = _on_disconnect
        _client.connect(config.mqtt_host, config.mqtt_port)
        _client.loop_start()
    return _client


def _on_connect(client: mqtt.Client, userdata, flags, rc, properties=None) -> None:
    if rc == 0:
        logger.info("Connected to MQTT broker")
    else:
        logger.error("MQTT connection failed with code %d", rc)


def _on_disconnect(client: mqtt.Client, userdata, flags, rc, properties=None) -> None:
    logger.warning("Disconnected from MQTT broker (rc=%d)", rc)


def disconnect() -> None:
    """Cleanly disconnect the MQTT client."""
    global _client
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()
        _client = None
        logger.info("MQTT client disconnected")
