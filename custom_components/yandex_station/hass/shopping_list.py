import logging
import re
import uuid

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant

from ..core.yandex_glagol import YandexGlagol

try:
    from homeassistant.const import EVENT_SHOPPING_LIST_UPDATED
except ImportError:
    EVENT_SHOPPING_LIST_UPDATED = "shopping_list_updated"

_LOGGER = logging.getLogger(__package__)

RE_SHOPPING = re.compile(r"^\d+\) (.+)$", re.MULTILINE)


def _alice_names(alice_data: str) -> list[str]:
    return RE_SHOPPING.findall(alice_data)


def shopping_for_remove(hass: HomeAssistant, alice_data: str) -> list[str]:
    """Indices (1-based) of completed-in-HA items still present in Alice's list."""
    alice_items = _alice_names(alice_data)
    shopping_data: ShoppingData = hass.data["shopping_list"]
    for_remove = [
        alice_items.index(item["name"])
        for item in shopping_data.items
        if item["complete"] and item["name"] in alice_items
    ]
    return [str(i + 1) for i in sorted(for_remove)]


def shopping_for_add(hass: HomeAssistant, alice_data: str) -> list[str]:
    shopping_data: ShoppingData = hass.data["shopping_list"]
    alice_items = _alice_names(alice_data)
    return [
        item["name"]
        for item in shopping_data.items
        if not item["complete"]
        and item["name"] not in alice_items
        and not item["id"].startswith("alice")
    ]


def shopping_for_delete_from_alice(hass: HomeAssistant, alice_data: str) -> list[str]:
    """Items present in Alice's list but not in HA — need to ask Alice to delete.

    This is the fix for #803: previously the local list was just overwritten
    with Alice's contents, so deletions made in HA silently came back on the
    next sync.
    """
    alice_items = _alice_names(alice_data)
    local_items = hass.data["shopping_list"].items
    return [name for name in alice_items if name not in {i["name"] for i in local_items}]


def shopping_save(hass: HomeAssistant, alice_data: str):
    alice_items = _alice_names(alice_data)
    shopping_data: ShoppingData = hass.data["shopping_list"]

    new_items = {
        name: {"name": name, "id": f"alice{uuid.uuid4().hex}", "complete": False}
        for name in alice_items
    }
    old_items = {i["name"]: i for i in shopping_data.items}

    shopping_data.items = list(new_items.values())
    hass.async_add_executor_job(shopping_data.save)

    # noinspection PyProtectedMember
    shopping_data._async_notify()

    for name, item in old_items.items():
        if name not in new_items:
            hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED, {"action": "remove", "item": item}
            )

    for name, item in new_items.items():
        if name not in old_items:
            hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED, {"action": "add", "item": item}
            )


async def shopping_sync(hass: HomeAssistant, glagol: YandexGlagol):
    if "shopping_list" not in hass.data:
        return

    payload = {"command": "sendText", "text": "Что в списке покупок"}

    try:
        card = await glagol.send(payload)

        # 1) Push HA-side deletions to Alice (issue #803).
        #    Previously this only handled completed items; the "deleted in HA"
        #    case was silently dropped, so items kept re-appearing.
        for_for_delete = shopping_for_delete_from_alice(hass, card["text"])
        if for_for_delete:
            # Build one command per item, safer than batching into one phrase.
            for name in for_for_delete:
                text = f"Удали из списка покупок {name}"
                await glagol.send({"command": "sendText", "text": text})
            card = await glagol.send(payload)

        # 2) Mark HA-side completions as done in Alice.
        for_remove = shopping_for_remove(hass, card["text"])
        if for_remove:
            # не удаляет больше 5 элементов за раз
            text = "Удали " + ", ".join(for_remove[:5])
            await glagol.send({"command": "sendText", "text": text})
            card = await glagol.send(payload)

        # 3) Add items that exist locally but not in Alice.
        for_add = shopping_for_add(hass, card["text"])
        if for_add:
            for item in for_add:
                # плохо работает, если добавлять всё сразу через запятую
                text = f"Добавь в список покупок {item}"
                await glagol.send({"command": "sendText", "text": text})
            card = await glagol.send(payload)

        shopping_save(hass, card["text"])
    except Exception as e:
        _LOGGER.error("shopping_sync", exc_info=e)
