"""Free, offline geographic calculations; the UI map uses OpenStreetMap."""
from math import asin, cos, radians, sin, sqrt

def haversine_km(lat1, lon1, lat2, lon2):
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371.0088 * 2 * asin(sqrt(a))

def interpolate(start, end, steps=24):
    return [(start[0]+(end[0]-start[0])*i/steps, start[1]+(end[1]-start[1])*i/steps) for i in range(steps+1)]

def route_overlap_percent(a_start, a_end, b_start, b_end, corridor_km=.7):
    a, b = interpolate(a_start, a_end), interpolate(b_start, b_end)
    def covered(points, other):
        return sum(min(haversine_km(*p, *q) for q in other) <= corridor_km for p in points)/len(points)
    return round(100*(covered(a,b)+covered(b,a))/2, 2)

def destination_compatibility(a_end, b_end):
    return round(max(0., 1.-haversine_km(*a_end, *b_end)/8.), 4)
