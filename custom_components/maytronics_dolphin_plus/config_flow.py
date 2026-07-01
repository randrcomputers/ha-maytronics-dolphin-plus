"""Config flow for Maytronics Dolphin Plus (local BLE)."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PROFILE,
    CONF_TRANSPORT,
    DEFAULT_NAME,
    DEFAULT_PROFILE,
    DEFAULT_TRANSPORT,
    DOMAIN,
    OPT_BLE_KEEPALIVE_SEC,
    OPT_STATE_POLL_SEC,
    PROFILE_BUOY,
    PROFILE_IOT,
    PROFILE_POP,
    TRANSPORT_IOT_GATT,
    TRANSPORT_NUS,
    TRANSPORT_POP,
)
from .options import get_integration_options

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$")


class MaytronicsDolphinPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            if not _MAC_RE.match(address):
                errors["base"] = "invalid_mac"
            else:
                address_fmt = dr.format_mac(address)
                await self.async_set_unique_id(address_fmt)
                self._abort_if_unique_id_configured()
                name = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: address_fmt,
                        CONF_NAME: name,
                        CONF_PROFILE: user_input.get(CONF_PROFILE, DEFAULT_PROFILE),
                        CONF_TRANSPORT: user_input.get(
                            CONF_TRANSPORT, DEFAULT_TRANSPORT
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        autocomplete="off",
                    )
                ),
                vol.Optional(CONF_NAME): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required(CONF_PROFILE, default=DEFAULT_PROFILE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=PROFILE_IOT, label="IoT / PS Plus (recommended)"
                            ),
                            selector.SelectOptionDict(
                                value=PROFILE_POP, label="POP cordless (experimental)"
                            ),
                            selector.SelectOptionDict(
                                value=PROFILE_BUOY, label="Buoy (experimental)"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_TRANSPORT, default=DEFAULT_TRANSPORT): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=TRANSPORT_NUS,
                                label="Nordic UART (6E400001 — default)",
                            ),
                            selector.SelectOptionDict(
                                value=TRANSPORT_IOT_GATT,
                                label="Alternate IoT GATT (fd5abba0)",
                            ),
                            selector.SelectOptionDict(
                                value=TRANSPORT_POP,
                                label="POP UART (fd5abca0)",
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return MaytronicsDolphinPlusOptionsFlow()


class MaytronicsDolphinPlusOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = get_integration_options(self.config_entry)
        schema = vol.Schema(
            {
                vol.Required(
                    OPT_BLE_KEEPALIVE_SEC,
                    default=current[OPT_BLE_KEEPALIVE_SEC],
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=600,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    OPT_STATE_POLL_SEC,
                    default=current[OPT_STATE_POLL_SEC],
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=600,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
