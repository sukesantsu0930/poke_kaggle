ATK_FLOWER_SHOWER = 215


class Protocol:
    """サブゴール実現の計測: Flower Shower（ミル主エンジン）を最初に打てたターン。
    デッキ設計_シャンデラ.md の S-0/E-1 に対応。"""

    name = "chandelure_first_flower_shower"

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
            if option.attackId == ATK_FLOWER_SHOWER:
                self._mark(obs, step, "selected Flower Shower")

    def observe_after_action(self, previous_obs, action, next_obs, actor, step):
        if self.achieved:
            return
        for log in next_obs.logs:
            if log.playerIndex == 0 and log.attackId == ATK_FLOWER_SHOWER:
                self._mark(next_obs, step, "logged Flower Shower")

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
