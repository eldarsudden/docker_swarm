from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        # Send sensitive input separately from the logged SSH command.
        result.update(
            self._low_level_execute_command(
                self._task.args["command"],
                in_data=(self._task.args["stdin"] + "\n").encode("utf-8"),
            )
        )
        result["changed"] = result["rc"] == 0
        if result["rc"] != 0:
            result.update(failed=True, msg="Remote command failed.")
        return result
