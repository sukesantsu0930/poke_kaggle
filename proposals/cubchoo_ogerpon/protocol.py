KEY_CARD_IDS = {
    506: "Cubchoo",
    117: "Cornerstone Mask Ogerpon ex",
    414: "Rocket's Articuno",
}


class Protocol:
    name = "key_cards_seen"

    def __init__(self):
        self.seen = {}
        self.events = []

    def observe_before_action(self, obs, action, actor, step):
        if actor == "agent0":
            self._scan_board(obs, step)

    def observe_after_action(self, previous_obs, action, next_obs, actor, step):
        if actor == "agent0":
            self._scan_board(next_obs, step)

    def _scan_board(self, obs, step):
        if obs.current is None:
            return
        player = obs.current.players[0]
        pokemon = list(player.active) + list(player.bench)
        for card in pokemon:
            if card is None or card.id not in KEY_CARD_IDS or card.id in self.seen:
                continue
            self.seen[card.id] = {
                "card_id": card.id,
                "name": KEY_CARD_IDS[card.id],
                "turn": obs.current.turn,
                "step": step,
            }
            self.events.append(self.seen[card.id])

    def trial_result(self):
        achieved = bool(self.seen)
        first = min((event["turn"] for event in self.events if event["turn"] is not None), default=None)
        return {
            "protocol": self.name,
            "achieved": achieved,
            "first_achieved_turn": first,
            "first_achieved_step": min((event["step"] for event in self.events), default=None),
            "seen_card_ids": sorted(self.seen),
            "events": self.events,
        }


def create_protocol():
    return Protocol()

