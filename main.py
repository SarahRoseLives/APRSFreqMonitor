from kivy.lang import Builder
from plyer import gps
from kivy.app import App
from kivy.clock import mainthread
from kivy.utils import platform
import aprslib
import re
import threading
import math

kv = '''
BoxLayout:
    orientation: 'vertical'

    Label:
        id: source_label
        text: 'Waiting for the first packet...'
        font_size: '40sp'
        halign: 'center'
        valign: 'middle'
        size_hint_y: 0.2
        bold: True

    Label:
        id: freq_label
        text: '000.000'
        font_size: '150sp'
        halign: 'center'
        valign: 'middle'
        size_hint_y: 0.6
        bold: True

    Label:
        id: comment_label
        text: ''
        font_size: '40sp'
        halign: 'center'
        valign: 'middle'
        size_hint_y: 0.2
'''

class GpsTest(App):

    excluded_callsigns = {'IWXSMW', 'ABQFFW', 'CLESVR', 'ILXSVR', 'EAXSVR'}
    excluded_addresses = {'NWS-WARN', 'NWS_WARN'}
    mhz_pattern = re.compile(r'(\d{2,3}\.\d{3})\s*mhz', re.IGNORECASE)

    current_latitude = None
    current_longitude = None

    def request_android_permissions(self):
        from android.permissions import request_permissions, Permission

        def callback(permissions, results):
            if all([res for res in results]):
                print("callback. All permissions granted.")
            else:
                print("callback. Some permissions refused.")

        request_permissions([Permission.ACCESS_COARSE_LOCATION,
                             Permission.ACCESS_FINE_LOCATION], callback)

    def build(self):
        try:
            gps.configure(on_location=self.on_location,
                          on_status=self.on_status)
        except NotImplementedError:
            import traceback
            traceback.print_exc()
            self.root.ids.source_label.text = 'GPS is not implemented for your platform'

        if platform == "android":
            print("gps.py: Android detected. Requesting permissions")
            self.request_android_permissions()

        # Start the GPS automatically
        self.start(1000, 0)

        # Start the APRS connection in a separate thread
        threading.Thread(target=self.connect_aprs, daemon=True).start()

        return Builder.load_string(kv)

    def start(self, minTime, minDistance):
        gps.start(minTime, minDistance)

    def stop(self):
        gps.stop()

    @mainthread
    def on_location(self, **kwargs):
        self.current_latitude = kwargs.get('lat')
        self.current_longitude = kwargs.get('lon')

    @mainthread
    def on_status(self, stype, status):
        pass

    def on_pause(self):
        gps.stop()
        return True

    def on_resume(self):
        gps.start(1000, 0)
        pass

    def connect_aprs(self):
        AIS = aprslib.IS("N0CALL")
        AIS.connect()
        AIS.consumer(self.callback, raw=True)

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        # Haversine formula to calculate distance between two coordinates
        R = 3958.8  # Radius of the Earth in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @mainthread
    def callback(self, packet):
        try:
            parsed_packet = aprslib.parse(packet)

            from_call = parsed_packet.get('from', '')
            to_call = parsed_packet.get('to', '')
            addressee_call = parsed_packet.get('addressee', '')
            latitude = parsed_packet.get('latitude', None)
            longitude = parsed_packet.get('longitude', None)
            comment = parsed_packet.get('comment', '')

            if comment and addressee_call not in self.excluded_addresses and from_call not in self.excluded_callsigns:
                if latitude and longitude and self.current_latitude and self.current_longitude:
                    distance = self.calculate_distance(self.current_latitude, self.current_longitude, latitude, longitude)
                    if distance <= 100:
                        freq_match = self.mhz_pattern.search(comment)
                        if freq_match:
                            frequency = freq_match.group(1)
                            self.root.ids.source_label.text = f"{from_call} de {addressee_call} {distance:.1f}mi"
                            self.root.ids.freq_label.text = frequency
                            self.root.ids.comment_label.text = comment.replace(freq_match.group(0), '').strip()
        except:
            pass

if __name__ == '__main__':
    GpsTest().run()
