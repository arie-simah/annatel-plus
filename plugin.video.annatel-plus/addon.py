import datetime
import os
import threading
import xml.etree.ElementTree as ET
from urllib import request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

__ADDON__ = xbmcaddon.Addon()
__ADDON_NAME__ = __ADDON__.getAddonInfo('name')
__ADDON_PROFILE__ = xbmcvfs.translatePath(__ADDON__.getAddonInfo('profile'))

UPDATE_INTERVAL = 4 * 3600 * 1000


class Annatel():
    def __init__(self):
        self.username = __ADDON__.getSetting('username')
        self.password = __ADDON__.getSetting('password')
        self.m3u_path_setting = __ADDON__.getSetting('m3u_path')
        self.api_url = f"http://www.annatel.tv/api/getchannels?login={self.username}&password={self.password}"

    def reset(self):
        self.__init__()

    def get_credentials(self):
        return (self.username, self.password)

    def check_credentials(self):
        if not self.username or not self.password:
            annatel_notification("No Credentials", "danger")
            return False

        r = request.urlopen(self.api_url)
        data = r.read()
        tree = ET.fromstring(data)

        if "un utilisateur premium pour utiliser" in  tree.find("channel").find("name").text:
            annatel_notification("Wrong Credentials", 'danger')
            return False

        annatel_notification("Login successful")
        return True

    def generate_m3u_file(self):

        annatel_notification("Updating links...")

        r = request.urlopen(self.api_url)
        data = r.read()
        tree = ET.fromstring(data)

        m3u_list = []
        m3u_list.append("#EXTM3U")

        for channel in tree.findall('*'):
            name = channel.find('name').text
            logo = channel.find('logo').text
            url = channel.find('url').text

            m3u_list.append(f'#EXTINF:1 tvg-logo="{logo}",{name.replace("é", "e").replace(" ", "_").replace("è", "e")}')
            m3u_list.append(url)
        
        m3u_string = '\n'.join(m3u_list)
        
        # Use the configured path or fallback to platform-appropriate paths
        if self.m3u_path_setting:
            if self.m3u_path_setting.startswith('special://'):
                # Translate Kodi special paths to real filesystem paths
                base_path = xbmcvfs.translatePath(self.m3u_path_setting)
            else:
                # Use the path as-is if it's already a filesystem path
                base_path = self.m3u_path_setting
        else:
            # Platform-specific fallback paths that are accessible to IPTV Simple
            try:
                # Try Android media path first
                base_path = "/storage/emulated/0/Android/media/"
                if not os.path.exists(base_path):
                    # Fallback to userdata if Android path doesn't exist
                    base_path = xbmcvfs.translatePath("special://userdata/")
            except:
                base_path = xbmcvfs.translatePath("special://userdata/")
            
        # Ensure the directory exists
        if not xbmcvfs.exists(base_path):
            xbmcvfs.mkdirs(base_path)
            
        m3u_path = os.path.join(base_path, "channels.m3u")
        
        # Log the actual path for debugging
        xbmc.log(f"Annatel+: Saving M3U file to: {m3u_path}", xbmc.LOGINFO)

        # Use Kodi's VFS for better cross-platform compatibility
        try:
            with xbmcvfs.File(m3u_path, 'w') as f1:
                f1.write(m3u_string.encode('utf-8'))
        except Exception as e:
            # Fallback to regular file operations if VFS fails
            xbmc.log(f"Annatel+: VFS write failed, using fallback: {str(e)}", xbmc.LOGWARNING)
            with open(m3u_path, 'w', encoding='utf-8') as f1:
                f1.write(m3u_string)
        
        annatel_notification("Links Updated")
        return m3u_path

    @staticmethod
    def annatel_configuration():
        __ADDON__.openSettings(__ADDON_NAME__)


class IPTV():
    def __init__(self):
        # Force IPTV Simple Addon Enable 
        xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method": "Addons.SetAddonEnabled","id":7,"params":{"addonid": "pvr.iptvsimple","enabled":true}}')
        try:
            # Get Addon (should be enabled)
            self.addon = xbmcaddon.Addon("pvr.iptvsimple")
        except:
            xbmcgui.Dialog().ok("Annatel+", "PVR IPTVSimple is Disable. Plase enable and restart Kodi")
            return None

    def load_files(self, m3u_file):
        self.addon.setSetting("m3uPathType", "0")
        self.addon.setSetting("m3uPath", m3u_file)

    def force_reload(self):
        # Use JSON execution to disable and enable IPTV Simple Addon
        xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method": "Addons.SetAddonEnabled","id":7,"params":{"addonid": "pvr.iptvsimple","enabled":false }}')
        xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method": "Addons.SetAddonEnabled","id":7,"params":{"addonid": "pvr.iptvsimple","enabled":true }}')


def annatel_notification(text, mode=None):
    if mode == 'warning':
        icon = xbmcgui.NOTIFICATION_WARNING
    elif mode == 'danger':
        icon = xbmcgui.NOTIFICATION_ERROR
    else:
        icon = __ADDON__.getAddonInfo('icon')
    xbmcgui.Dialog().notification("Annatel+", text, icon, 5, True)


def refresh_links(iptv, annatel):
    while True:
        try:
            m3u_file = annatel.generate_m3u_file()
            iptv.load_files(m3u_file)

        except Exception as e:
            annatel_notification(str(e))

        xbmc.sleep(UPDATE_INTERVAL)


def main():

    iptv = IPTV()
    annatel = Annatel()
    
    if not iptv:
        return
    
    if not annatel.check_credentials():
        response = xbmcgui.Dialog().yesno("Annatel+", "Open Annatel+ settings?\n(Enter your Annatel's identifiers and restart Kodi)")
        if response:
            annatel.annatel_configuration()
    else:
        threading.Thread(target=refresh_links, args=(iptv, annatel)).start()

main()
