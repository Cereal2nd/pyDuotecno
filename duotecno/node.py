class Node:
    def __init__(self, address: int, numUnits: int) -> None:
        pass

    async def requestUnits(self) -> None:
        for i in range(self.numUnits - 1):
            self.write(f"[209,2,{self.address},{i}]")
