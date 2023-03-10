import time
import logging
from Profile import Profile
from KilnZones import KilnZones, SimZone
import DataFilter


log_level = logging.DEBUG
log_format = '%(asctime)s %(levelname)s %(name)s: %(message)s'

log = logging.getLogger(__name__)


class Controller:
    def __init__(self, file: str, notifier):
        self.notifier = notifier
        self.profile = Profile(file)
        zone = SimZone()
        self.loop_delay = 10

        self.long_t_t_h = []
        self.data_filter = DataFilter
        self.start_time_ms = None

        if zone.sim_speedup is not None:
            self.loop_delay = self.loop_delay / zone.sim_speedup
            log.info('Sim speed up factor is ' + str(zone.sim_speedup))

        self.zones = [zone]
        self.kiln_zones = KilnZones(self.zones)

        log.info('Controller initialized.')

    def control_loop(self):
        self.start_time_ms = time.time() * 1000
        self.__zero_heat_zones()
        while True:
            t_t_h = self.kiln_zones.get_times_temps_heat_for_zones()

            self.long_t_t_h = self.long_t_t_h + t_t_h['Zone 1']
            if len(self.long_t_t_h) > 100:
                self.long_t_t_h.pop(0)
            log.debug('Long_data: ' + str(len(self.long_t_t_h)))
            filter_result = self.data_filter.linear(self.long_t_t_h)
            log.debug(filter_result)
            if filter_result is not None:
                log.info(str(filter_result['slope'] * 3.6e6) + ' Degrees per hour.')

            median_result = self.data_filter.median(t_t_h['Zone 1'])
            log.debug(median_result)
            best_temp = median_result['median']
            best_time = (t_t_h['Zone 1'][-1]['time_ms'] + t_t_h['Zone 1'][-1]['time_ms']) / 2
            target = self.profile.get_target_temperature((best_time - self.start_time_ms) / 1000)

            temp_error = best_temp - target

            heats = self.__update_zones_heat(t_t_h, temp_error)
            self.kiln_zones.set_heat_for_zones(heats)
            self.__notify(t_t_h)
            time.sleep(self.loop_delay)

    def __zero_heat_zones(self):
        heats = []
        for i in range(len(self.zones)):
            heats.append(0)
        self.kiln_zones.set_heat_for_zones(heats)

    def __update_zones_heat(self, t_t_h: dict, temp_error: float) -> list:
        latest_t_t_h = t_t_h['Zone 1']
        temp = latest_t_t_h[0]['temperature']
        heat = 1
        if temp_error > 0:
            heat = 0
        heats = []
        for i in range(len(self.zones)):
            heats.append(heat)

        return heats

    def __notify(self, t_t_h: dict):
        self.notifier.update(t_t_h)


class notifier:
    def update(self, message):
        log.info(message)


#  This is for testing
if __name__ == '__main__':
    controller = Controller("test-fast.json", notifier())
    controller.control_loop()
