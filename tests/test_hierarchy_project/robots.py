from base import Robot

class RobotAspirateur(Robot):
    def travailler(self):
        print("J'aspire le salon")

class RobotCuisinier(Robot):
    def travailler(self):
        print("Je fais des crêpes")

# Cette classe est héritée par RobotCuisinierInutile mais jamais utilisée
class BaseInutile:
    def rien_faire(self):
        pass

class RobotCuisinierInutile(BaseInutile):
    def travailler(self):
        pass