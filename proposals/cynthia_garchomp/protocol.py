ATK_CORKSCREW_DIVE = 531


class Protocol:
    """サブゴール実現の計測: Corkscrew Dive を最初に打てたターン。
    デッキ設計_ガブリアス.md の S-0 に対応。"""

    name = "garchomp_first_corkscrew_dive"

    def __init__(self):
        self.achieved = False
        self.first_achieved_turn = None
        self.first_achieved_step = None
        self.events = []

    def observe_before_action(self, obs, action, actor, step):
        if actor != "agent0" or obs.select is None:
            return
        for index in action:
            if not 0 <= index < len(obs.select.option):
                continue
            option = obs.select.option[index]
            if option.attackId == ATK_CORKSCREW_DIVE:
                self._mark(obs, step, "selected Corkscrew Dive")

    def observe_after_action(self, previous_obs, action, next_obs, actor, step):
        if self.achieved:
            return
        for log in next_obs.logs:
            if log.playerIndex == 0 and log.attackId == ATK_CORKSCREW_DIVE:
                self._mark(next_obs, step, "logged Corkscrew Dive")

    def _mark(self, obs, step, label):
        if self.achieved:
            return
        self.achieved = True
        self.first_achieved_step = step
        self.first_achieved_turn = obs.current.turn if obs.current is not None else None
        self.events.append({"step": step, "turn": self.first_achieved_turn, "event": label})

    def trial_result(self):
        return {
            "protocol": self.name,
            "achieved": self.achieved,
            "first_achieved_turn": self.first_achieved_turn,
            "first_achieved_step": self.first_achieved_step,
            "events": self.events,
        }


def create_protocol():
    return Protocol()
