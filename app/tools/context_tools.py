from __future__ import annotations

import asyncio


class ContextTools:
    def __init__(self, context, channel_id, user_id):
        self.context = context
        self.channel_id = str(channel_id)
        self.user_id = str(user_id)

    async def channel(self, channel_id=None):
        bot = self.context.bot
        target_id = int(channel_id or self.channel_id)
        channel = bot.get_channel(target_id) or await bot.fetch_channel(target_id)
        guild = getattr(channel, "guild", None)
        if guild is None or str(guild.id) != str(self.context.config.server_id):
            raise ValueError("Canal fora do servidor configurado.")
        member = guild.get_member(int(self.user_id)) or await guild.fetch_member(int(self.user_id))
        for actor in (member, guild.me):
            if actor is None:
                raise ValueError("Membro indisponivel.")
            permissions = channel.permissions_for(actor)
            if not permissions.view_channel or not permissions.read_message_history:
                raise ValueError("Sem permissao para consultar o canal.")
        # Never export restricted channel content to another audience.
        if str(target_id) != self.channel_id:
            public = channel.permissions_for(guild.default_role)
            if not public.view_channel or not public.read_message_history:
                raise ValueError("Consulte canais restritos dentro do proprio canal.")
        return channel

    @staticmethod
    def serialize(message):
        return {
            "message_id": str(message.id),
            "user_id": str(message.author.id),
            "user_name": message.author.display_name,
            "content": (message.content or "")[:1600],
            "created_at": message.created_at.isoformat(),
            "attachments": [{"name": a.filename, "url": a.url} for a in message.attachments[:3]],
            "reference_message_id": str(message.reference.message_id) if message.reference else None,
        }

    async def recent_messages(self, channel_id=None):
        channel = await self.channel(channel_id)
        messages = [self.serialize(m) async for m in channel.history(limit=5)]
        return {"channel_id": str(channel.id), "messages": list(reversed(messages))}

    async def message_count(self):
        channel = await self.channel()
        return await asyncio.to_thread(self.context.message_repository.count,
                                       channel.guild.id, self.user_id)

    async def _assign_role(self, role_id, reason):
        return await self._change_role(role_id, reason, remove=False)

    async def _change_role(self, role_id, reason, *, remove):
        channel = await self.channel()
        guild = channel.guild
        member = await guild.fetch_member(int(self.user_id))
        role = guild.get_role(role_id)
        if role is None:
            raise ValueError("Cargo configurado nao encontrado.")
        has_role = any(item.id == role_id for item in member.roles)
        if has_role != remove:
            return {"status": "already_absent" if remove else "already_assigned",
                    "user_id": self.user_id, "role_id": str(role_id)}
        bot_member = guild.me
        if not bot_member.guild_permissions.manage_roles:
            raise ValueError("Bot sem permissao Gerenciar Cargos.")
        if role.is_default() or role.managed or role >= bot_member.top_role:
            raise ValueError("Cargo nao pode ser alterado pela hierarquia do bot.")
        action = member.remove_roles if remove else member.add_roles
        await action(role, reason="LLM: " + reason[:400], atomic=True)
        return {"status": "removed" if remove else "assigned", "user_id": self.user_id,
                "role_id": str(role_id), "role_name": role.name}

    async def give_platelminto(self, reason):
        return await self._assign_role(1194700649301020763, reason)

    async def give_homunco(self, reason):
        return await self._assign_role(1194723205022232637, reason)

    async def give_quarentena(self, reason):
        return await self._assign_role(1194720159416467527, reason)

    async def remove_platelminto(self, reason):
        return await self._change_role(1194700649301020763, reason, remove=True)

    async def remove_homunco(self, reason):
        return await self._change_role(1194723205022232637, reason, remove=True)

    async def remove_quarentena(self, reason):
        return await self._change_role(1194720159416467527, reason, remove=True)

    async def get_message(self, message_id, channel_id=None):
        channel = await self.channel(channel_id)
        return self.serialize(await channel.fetch_message(int(message_id)))

    async def first_count(self, user_id=None):
        await self.channel()
        target = str(user_id or self.user_id)
        row = await asyncio.to_thread(self.context.first_repository.get_user, target)
        return {"user_id": target, "user_name": row[0] if row else None,
                "first_count": row[1] if row else 0, "registered": row is not None}

    async def _member_identity(self, guild, user_id, stored_username):
        member = guild.get_member(int(user_id))
        if member is None and hasattr(guild, "fetch_member"):
            try:
                member = await guild.fetch_member(int(user_id))
            except Exception:
                member = None
        if member is None:
            return {"username": stored_username, "nickname": None}
        return {
            "username": getattr(member, "name", None) or stored_username,
            "nickname": getattr(member, "nick", None),
        }

    async def top_firsts(self):
        channel = await self.channel()
        rows = await asyncio.to_thread(
            self.context.first_repository.get_top_users_with_ids, 25
        )
        ranking = []
        for position, (user_id, stored_username, count) in enumerate(rows, start=1):
            identity = await self._member_identity(
                channel.guild, user_id, stored_username
            )
            ranking.append({
                "position": position,
                "user_id": str(user_id),
                **identity,
                "first_count": count,
            })
        return {
            "server_id": str(channel.guild.id),
            "total_listed": len(ranking),
            "ranking": ranking,
        }

    async def monthly_firsts(self, year, month):
        if not 1970 <= year <= 2100 or not 1 <= month <= 12:
            raise ValueError("Ano ou mes invalido.")
        channel = await self.channel()
        rows = await asyncio.to_thread(
            self.context.first_repository.get_monthly_firsts, year, month
        )
        ranking = []
        for position, (user_id, stored_username, count) in enumerate(rows, start=1):
            identity = await self._member_identity(
                channel.guild, user_id, stored_username
            )
            ranking.append({
                "position": position,
                "user_id": str(user_id),
                **identity,
                "first_count": count,
            })
        return {
            "server_id": str(channel.guild.id),
            "year": year,
            "month": month,
            "total_unique_users": len(ranking),
            "ranking": ranking,
        }

    @staticmethod
    def _asset_url(asset):
        return str(asset.url) if asset is not None and getattr(asset, "url", None) else None

    @staticmethod
    def _iso(value):
        return value.isoformat() if value is not None and hasattr(value, "isoformat") else None

    async def _fetch_profile_user(self, user_id):
        bot = self.context.bot
        cached_user = bot.get_user(int(user_id)) if hasattr(bot, "get_user") else None
        if hasattr(bot, "fetch_user"):
            try:
                # REST fetch exposes fields that may not exist on a cached user,
                # notably banner and accent color.
                return await bot.fetch_user(int(user_id))
            except Exception:
                pass
        user = cached_user
        if user is None:
            raise ValueError("Usuario nao encontrado.")
        return user

    async def _message_activity(self, guild, member, user_id):
        """Scan a bounded, permission-checked window of server history."""
        bot_member = getattr(guild, "me", None)
        messages = []
        channels_scanned = 0
        messages_scanned = 0
        channels = list(getattr(guild, "text_channels", ()) or ())
        for channel in channels[:30]:
            if bot_member is None or not hasattr(channel, "permissions_for"):
                continue
            try:
                bot_permissions = channel.permissions_for(bot_member)
                user_permissions = channel.permissions_for(member)
                if not (bot_permissions.view_channel and bot_permissions.read_message_history):
                    continue
                if not (user_permissions.view_channel and user_permissions.read_message_history):
                    continue
                history = getattr(channel, "history", None)
                if history is None:
                    continue
                channels_scanned += 1
                async for message in history(limit=20):
                    messages_scanned += 1
                    if str(getattr(getattr(message, "author", None), "id", "")) != str(user_id):
                        continue
                    messages.append({
                        "message_id": str(message.id),
                        "channel_id": str(channel.id),
                        "channel_name": getattr(channel, "name", None),
                        "content": (getattr(message, "content", "") or "")[:1600],
                        "created_at": self._iso(getattr(message, "created_at", None)),
                        "attachments": [
                            {"name": attachment.filename, "url": attachment.url}
                            for attachment in list(getattr(message, "attachments", ()) or ())[:3]
                        ],
                    })
                    if len(messages) >= 10:
                        break
                if len(messages) >= 10:
                    break
            except Exception:
                # A channel can disappear or deny history between the permission
                # check and the request. It must not abort the profile lookup.
                continue
        messages.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return {
            "messages": messages,
            "matching_messages": len(messages),
            "channels_scanned": channels_scanned,
            "messages_scanned": messages_scanned,
            "truncated": len(messages) >= 10,
        }

    async def user_profile(self):
        """Return Discord data available for the user who sent the current message."""
        current_channel = await self.channel()
        guild = current_channel.guild
        target_id = int(self.user_id)
        member = guild.get_member(target_id)
        if member is None and hasattr(guild, "fetch_member"):
            member = await guild.fetch_member(target_id)
        if member is None:
            raise ValueError("O usuario nao pertence mais a este servidor.")
        try:
            user = await self._fetch_profile_user(target_id)
        except Exception:
            # A cached Member still contains the public identity if the REST
            # fetch is temporarily unavailable; banner/accent data may be absent.
            user = member

        timed_out_until = getattr(member, "communication_disabled_until", None)
        if timed_out_until is None:
            timed_out_until = getattr(member, "timed_out_until", None)
        permissions = getattr(member, "guild_permissions", None)
        permission_names = (
            "administrator", "manage_guild", "manage_messages", "moderate_members",
            "kick_members", "ban_members", "mention_everyone", "attach_files",
        )
        membership = {
            "server_id": str(guild.id),
            "server_name": getattr(guild, "name", None),
            "joined_at": self._iso(getattr(member, "joined_at", None)),
            "nickname": getattr(member, "nick", None),
            "display_name": getattr(member, "display_name", None),
            "roles": [
                getattr(role, "name", str(role))
                for role in list(getattr(member, "roles", ()) or ())
                if getattr(role, "name", None) != "@everyone"
            ][:20],
            "pending": getattr(member, "pending", None),
            "premium_since": self._iso(getattr(member, "premium_since", None)),
            "timed_out_until": self._iso(timed_out_until),
            "permissions": {
                name: bool(getattr(permissions, name))
                for name in permission_names
                if permissions is not None and hasattr(permissions, name)
            },
        }
        activity = await self._message_activity(guild, member, target_id)
        return {
            "user_id": str(user.id),
            "username": getattr(user, "name", None),
            "global_name": getattr(user, "global_name", None),
            "display_name": getattr(user, "display_name", None),
            "mention": getattr(user, "mention", None),
            "discriminator": getattr(user, "discriminator", None),
            "bot": bool(getattr(user, "bot", False)),
            "system": bool(getattr(user, "system", False)),
            "created_at": self._iso(getattr(user, "created_at", None)),
            "avatar_url": self._asset_url(getattr(user, "avatar", None)),
            "banner_url": self._asset_url(getattr(user, "banner", None)),
            "display_avatar_url": self._asset_url(getattr(user, "display_avatar", None)),
            "server_avatar_url": self._asset_url(getattr(member, "avatar", None)),
            "server_banner_url": self._asset_url(getattr(member, "banner", None)),
            "accent_color": str(getattr(user, "accent_color", None))
            if getattr(user, "accent_color", None) is not None else None,
            "public_flags": str(getattr(user, "public_flags", None))
            if getattr(user, "public_flags", None) is not None else None,
            "bio": None,
            "pronouns": None,
            "membership": membership,
            "message_activity": activity,
            "unavailable_fields": [
                "bio", "pronouns", "lifetime_message_count",
            ],
            "limitations": (
                "discord.py nao expoe bio ou pronomes pelo objeto User/Member, "
                "e o Discord nao fornece uma contagem historica total de mensagens. "
                "A atividade acima e uma amostra limitada ao historico que o bot pode ler."
            ),
        }

    async def memory_search(self, scope, query="", user_id=None, channel_id=None):
        await self.channel()
        if scope == "channel":
            await self.channel(channel_id)
        service = self.context.ai.memory
        target = {"server": "server", "channel": str(channel_id or self.channel_id),
                  "user": str(user_id or self.user_id)}[scope]
        internal_scope = "global" if scope == "server" else scope
        async with service.lock:
            state = service._load_state()
            entries = [entry for entry in state.get("__memory_entries__", [])
                       if entry.get("scope") == internal_scope
                       and str(entry.get("scope_id")) == target and not service._expired(entry)]
            if scope == "server":
                entries += [{"category": "Custom", "value": entry.get("content", "")}
                            for entry in state.get("__custom_memory__", [])]
            terms = query.casefold().split()
            found = [entry for entry in entries if all(
                term in (str(entry.get("key", "")) + " " + str(entry.get("value", ""))).casefold()
                for term in terms)]
            return {"scope": scope, "scope_id": target, "total": len(found),
                    "results": [{key: (str(e[key])[:2000] if key == "value" else e[key])
                                 for key in ("key", "value", "category", "confidence", "updated_at") if key in e}
                                for e in found[:5]]}
