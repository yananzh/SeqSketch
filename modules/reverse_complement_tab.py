from modules.complement_tab import ComplementTab


class ReverseComplementTab(ComplementTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_mode("Reverse Complement")
