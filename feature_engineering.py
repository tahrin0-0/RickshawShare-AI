from route_service import destination_compatibility, haversine_km, route_overlap_percent

def preferences_compatible(a, b):
    def accepts(ride, other):
        pref = (ride.gender_preference or "any").lower()
        return pref == "any" or pref == other.user.gender.lower()
    return int(accepts(a,b) and accepts(b,a))

def build_pair_features(a, b):
    ap=(a.pickup_latitude,a.pickup_longitude); bp=(b.pickup_latitude,b.pickup_longitude)
    ad=(a.destination_latitude,a.destination_longitude); bd=(b.destination_latitude,b.destination_longitude)
    return {"pickup_distance_km":round(haversine_km(*ap,*bp),3),
            "time_difference_min":round(abs((a.preferred_time-b.preferred_time).total_seconds())/60,2),
            "route_overlap_percent":route_overlap_percent(ap,ad,bp,bd),
            "destination_compatibility":destination_compatibility(ad,bd),
            "preference_compatible":preferences_compatible(a,b)}
