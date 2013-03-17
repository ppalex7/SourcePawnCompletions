# Auto-increment version plugins for sublimetext 2 By ppalex.
# https://forums.alliedmods.net/showthread.php?t=207210
import sublime, sublime_plugin

class EventDump(sublime_plugin.EventListener):
	def on_pre_save(self, view):
        	strName = view.file_name()
        	strExt = strName[strName.rfind(".")+1:]
        	if strExt == "sp":
            		view.run_command("ver_inc")

class VerIncCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		# You can change PLUGIN_VERSION according to your needs.
		region = self.view.find("^#define\s+(?:PLUGIN_)?VERSION\s+\"\d{1,2}\.\d{1,2}\.\d{1,3}\"", 0)
		if region != None:
			strLine = self.view.substr(region)
			rIndex1 = strLine.rfind(".")
			rIndex2 = strLine.rfind("\"")
			sBuild = strLine[rIndex1+1:rIndex2]
			try:
				iBuild = int(sBuild)
				iBuild += 1
				self.view.replace(edit, region, strLine[:rIndex1+1] + str(iBuild) + "\"")
			except ValueError:
				pass
