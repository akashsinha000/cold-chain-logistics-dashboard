class LocalMessage:
    def __init__(self, content="", tool_calls=None, name=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.name = name


class LocalToolMessage(LocalMessage):
    pass