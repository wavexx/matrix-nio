# -*- coding: utf-8 -*-

# Copyright © 2018-2019 Damir Jelić <poljar@termina.org.uk>
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted, provided that the
# above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from typing import Optional

import attr
from copy import deepcopy

from ..messages import ToDeviceMessage
from ..schemas import Schemas
from .misc import verify


@attr.s
class RoomEncryptedEvent(object):
    @classmethod
    @verify(Schemas.room_encrypted)
    def parse_event(cls, event_dict):
        content = event_dict["content"]

        if content["algorithm"] == "m.olm.v1.curve25519-aes-sha2":
            return OlmEvent.from_dict(event_dict)
        elif content["algorithm"] == "m.megolm.v1.aes-sha2":
            return MegolmEvent.from_dict(event_dict)

        return None


@attr.s
class OlmEvent(RoomEncryptedEvent):
    """An Olm encrypted event.

    Olm events are used to exchange end to end encrypted messages between two
    devices. They will mostly contain encryption keys to establish a Megolm
    session for a room.

    nio users will never see such an event under normal circumstances since
    decrypting this event will produce an event of another type.

    Attributes:
        sender (str): The fully-qualified ID of the user who sent this
            event.
        sender_key (str, optional): The public key of the sender that was used
            to establish the encrypted session. Is only set if decrypted is
            True, otherwise None.
        ciphertext (str): The undecrypted ciphertext of the event.
        transaction_id (str, optional): The unique identifier that was used
            when the message was sent. Is only set if the message was sent from
            our own device, otherwise None.

    """

    sender = attr.ib()
    sender_key = attr.ib()
    ciphertext = attr.ib()
    transaction_id = attr.ib(default=None)

    @classmethod
    @verify(Schemas.room_olm_encrypted)
    def from_dict(cls, event_dict):
        content = event_dict["content"]

        ciphertext = content["ciphertext"]
        sender_key = content["sender_key"]

        tx_id = (event_dict["unsigned"].get("transaction_id", None)
                 if "unsigned" in event_dict else None)

        return cls(event_dict["sender"], sender_key, ciphertext, tx_id)


@attr.s
class RoomKeyEvent(object):
    """Event containing a megolm room key that got sent to us.

    Attributes:
        sender (str): The sender of the event.
        sender_key (str): The key of the sender that sent the event.
        room_id (str): The room ID of the room to which the session key
            belongs to.
        session_id (str): The session id of the session key.
        algorithm: (str): The algorithm of the session key.

    """

    source = attr.ib(type=str)
    sender = attr.ib(type=str)
    sender_key = attr.ib(type=str)
    room_id = attr.ib(type=str)
    session_id = attr.ib(type=str)
    algorithm = attr.ib(type=str)

    @classmethod
    @verify(Schemas.room_key_event)
    def from_dict(cls, event_dict, sender, sender_key):
        event_dict = deepcopy(event_dict)
        event_dict.pop("keys")

        content = event_dict["content"]
        content.pop("session_key")

        return cls(
            event_dict,
            sender,
            sender_key,
            content["room_id"],
            content["session_id"],
            content["algorithm"]
        )


@attr.s
class ForwardedRoomKeyEvent(RoomKeyEvent):
    """Event containing a room key that got forwarded to us.

    Attributes:
        sender (str): The sender of the event.
        sender_key (str): The key of the sender that sent the event.
        room_id (str): The room ID of the room to which the session key
            belongs to.
        session_id (str): The session id of the session key.
        algorithm: (str): The algorithm of the session key.

    """

    @classmethod
    @verify(Schemas.forwarded_room_key_event)
    def from_dict(cls, event_dict, sender, sender_key):
        """Create a ForwardedRoomKeyEvent from a event dictionary.

        Args:
            event_dict (Dict): The dictionary containing the event.
            sender (str): The sender of the event.
            sender_key (str): The key of the sender that sent the event.
        """
        event_dict = deepcopy(event_dict)
        content = event_dict["content"]
        content.pop("session_key")

        return cls(
            event_dict,
            sender,
            sender_key,
            content["room_id"],
            content["session_id"],
            content["algorithm"]
        )


@attr.s
class MegolmEvent(RoomEncryptedEvent):
    """An undecrypted Megolm event.

    MegolmEvents are presented to library users only if the library fails
    to decrypt the event because of a missing session key.

    MegolmEvents can be stored for later use. If a RoomKeyEvent is later on
    received with a session id that matches the session_id of this event
    decryption can be retried.

    Attributes:
        event_id (str): A globally unique event identifier.
        sender (str): The fully-qualified ID of the user who sent this
            event.
        server_timestamp (int): Timestamp in milliseconds on originating
            homeserver when this event was sent.
        sender_key (str, optional): The public key of the sender that was used
            to establish the encrypted session. Is only set if decrypted is
            True, otherwise None.
        device_id (str): The unique identifier of the device that was used to
            encrypt the event.
        session_id (str): The unique identifier of the session that
            was used to encrypt the message.
        ciphertext (str): The undecrypted ciphertext of the event.
        algorithm (str): The encryption algorithm that was used to encrypt the
            message.
        room_id (str): The unique identifier of the room in which the message
            was sent.
        transaction_id (str, optional): The unique identifier that was used
            when the message was sent. Is only set if the message was sent from
            our own device, otherwise None.
        decrypted (bool, optional): Boolean deciding if the event was
            decrypted, always false. Only here to be consistent with room
            events.
        verified (bool, optional): Boolean deciding if the event was sent from
            a verified device and passed verification, always false. Only here
            to be consistent with room events.

    """

    event_id = attr.ib()
    sender = attr.ib()
    server_timestamp = attr.ib()

    sender_key = attr.ib()
    device_id = attr.ib()
    session_id = attr.ib()
    ciphertext = attr.ib()
    algorithm = attr.ib()
    room_id = attr.ib(default="")
    transaction_id = attr.ib(default=None)

    decrypted = attr.ib(default=False, init=False)
    verified = attr.ib(default=False, init=False)

    @classmethod
    @verify(Schemas.room_megolm_encrypted)
    def from_dict(cls, event_dict):
        """Create a MegolmEvent from a dictionary.

        Args:
            event_dict (Dict): Dictionary containing the event.

        Returns a MegolmEvent if the event_dict contains a valid event or a
        BadEvent if it's invalid.
        """
        content = event_dict["content"]

        ciphertext = content["ciphertext"]
        sender_key = content["sender_key"]
        session_id = content["session_id"]
        device_id = content["device_id"]
        algorithm = content["algorithm"]

        room_id = event_dict.get("room_id", None)
        tx_id = (event_dict["unsigned"].get("transaction_id", None)
                 if "unsigned" in event_dict else None)

        return cls(
            event_dict["event_id"],
            event_dict["sender"],
            event_dict["origin_server_ts"],
            sender_key,
            device_id,
            session_id,
            ciphertext,
            algorithm,
            room_id,
            tx_id
        )

    def as_key_request(self, user_id, requesting_device_id, request_id=None):
        # type: (str, str, Optional[str]) -> ToDeviceMessage
        """Make a to-device message for a room key request.

        MegolmEvents are presented to library users only if the library fails
        to decrypt the event because of a missing session key.

        A missing key can be requested later on by sending a key request, this
        method creates a ToDeviceMessage that can be sent out if such a request
        should be made.

        Args:
            user_id (str): The user id of the user that should receive the key
                request.

        """
        content = {
            "action": "request",
            "body": {
                "algorithm": self.algorithm,
                "session_id": self.session_id,
                "room_id": self.room_id,
                "sender_key": self.sender_key
            },
            "request_id": request_id or self.session_id,
            "requesting_device_id": requesting_device_id,
        }

        return ToDeviceMessage(
            "m.room_key_request",
            user_id,
            "*",
            content
        )
