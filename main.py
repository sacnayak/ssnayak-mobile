# Imports
import os
import jinja2
import webapp2
import logging
import json
import urllib
import MySQLdb
import math

# Import the Flask Framework
from flask import Flask
#Import datetime
from datetime import datetime

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

# Define your production Cloud SQL instance information.
_INSTANCE_NAME = 'ssnayak-mobile:ssnayak-mobile' #ProjectID:Project Instance Name
_DB_NAME = 'QuantifiedSelf'
_USER = 'root' # or whatever other user account you created

# the table where activities are logged
_ACTIVITY = 'plugin_google_activity_recognition'
# the table where locations are logged
_LOCATIONS = 'locations'
# the distance that determins new locations
_EPSILON = 1

_THETA = 1

if (os.getenv('SERVER_SOFTWARE') and
    os.getenv('SERVER_SOFTWARE').startswith('Google App Engine/')):
    _DB = MySQLdb.connect(unix_socket='/cloudsql/' + _INSTANCE_NAME, db=_DB_NAME, user=_USER, charset='utf8')
else:
    _DB = MySQLdb.connect(host='173.194.255.125', port=3306, db=_DB_NAME, user=_USER, charset='utf8')#add passwd to run on local

_DEVICE_ID = '44a33712-0093-4598-9bc1-ed4d396646eb'

app = Flask(__name__)


@app.route('/')
def index():
    template = JINJA_ENVIRONMENT.get_template('templates/index.html')

    cursor = _DB.cursor()
    #cursor.execute('SHOW TABLES')
    
    #logging.info(cursor.fetchall())
    #_DB.close()
    logging.info("making queries")
    make_and_print_query(cursor, 'SHOW TABLES', 'Show the names of all tables')
    query = 'SHOW TABLES'
    rows = make_query(cursor, query)
    queries = [{"query": query, "results": rows}]

	#Days when location data was collected
    query = 'SELECT FROM_UNIXTIME' + '(timestamp/1000,\'%Y-%m-%d\')' + ' AS day_with_data, COUNT(*) AS records FROM locations' + ' GROUP by day_with_data;'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #Select Battery stuff
    #query = 'SELECT FROM_UNIXTIME' + '(timestamp/1000,\'%Y-%m-%d\')' + ' AS day_with_data, COUNT(*) AS records FROM battery' + ' GROUP by day_with_data;'
    #data = make_query(cursor, query)
    #queries = queries + [{"query": query, "results": data}]

    # turns a unix timestamp into Year-month-day format
    day = "FROM_UNIXTIME(timestamp/1000,\'%Y-%m-%d\')"
    # turns a unix timestamp into Hour:minute format
    time_of_day = "FROM_UNIXTIME(timestamp/1000,\'%H:%i\')"
    # calculates the difference between two timestamps in seconds
    elapsed_seconds = "(max(timestamp)-min(timestamp))/1000"
    # the name of the table our query should run on
    table = _ACTIVITY
    # turns a unix timestamp into Year-month-day Hour:minute format
    day_and_time_of_day = "FROM_UNIXTIME(timestamp/100, \'%Y-%m-%d %H:%i\')"
    # Groups the rows of a table by day and activity (so there will be one 
    # group of rows for each activity that occurred each day.  
    # For each group of rows, the day, time of day, activity name, and 
    # elapsed seconds (difference between maximum and minimum) is calculated, 
    query = "SELECT {0} AS day, {1} AS time_of_day, activity_name, {2} AS time_elapsed_seconds FROM {3} WHERE device_id=\'{4}\'  GROUP BY day, activity_name, {5}".format(day, time_of_day, elapsed_seconds, table, _DEVICE_ID, day_and_time_of_day)
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #Identifying common locations
    query = "SELECT double_latitude, double_longitude FROM {0} WHERE device_id = \'{1}\'".format(_LOCATIONS, _DEVICE_ID)
    locations = make_query(cursor, query)
    #queries = queries + [{"query": query, "results": locations}]

    bins = bin_locations(locations, _EPSILON)
    for location in bins: 
        queries = queries + [{"query": query, "results": location}]

    time_of_day = "FROM_UNIXTIME(timestamp/1000,'%H:%i')"
    day = "FROM_UNIXTIME(timestamp/1000,'%Y-%m-%d')"
    query = "SELECT {0} as day, {1} as time_of_day, double_latitude, double_longitude FROM {2} WHERE device_id = '{3}' GROUP BY day, time_of_day".format(day, time_of_day, _LOCATIONS, _DEVICE_ID)
    locations = make_query(cursor, query)

    day_and_time_of_day = "FROM_UNIXTIME(timestamp/100, '%Y-%m-%d %H')"
    elapsed_seconds = "(max(timestamp)-min(timestamp))/1000"
    query = "SELECT {0} as day, {1} as time_of_day, activity_name, {2} as time_elapsed_seconds FROM  {3} WHERE device_id = '{4}' GROUP BY day, activity_name, {5}".format(day, time_of_day, elapsed_seconds, _ACTIVITY, _DEVICE_ID, day_and_time_of_day)
    activities = make_query(cursor, query)

    # now we want to associate activities with locations. This will update the
    # bins list with activities.
    group_activities_by_location(bins, locations, activities, _EPSILON)

   	#Get times of day where activity is logged
    query = "SELECT {0} as time_of_day FROM {1} WHERE device_id = '{2}' GROUP BY time_of_day".format(time_of_day, _ACTIVITY, _DEVICE_ID)
    activity_times = make_query(cursor, query)
    
    query = "SELECT {0} as time_of_day, activity_name FROM {1}".format(time_of_day,_ACTIVITY)
    all_activities = make_query(cursor, query)
    time_tuples = group_activities_by_time(all_activities)

    context = {"queries": queries, "times" : time_tuples}
    return template.render(context)

@app.route('/about')
def about():
    template = JINJA_ENVIRONMENT.get_template('templates/about.html')
    cursor = _DB.cursor()
    logging.info("Table Descriptions")

    #applications_foreground
    query = 'DESCRIBE applications_foreground'
    data = make_query(cursor, query)
    queries = [{"query": query, "results": data}]

    #applications_history
    query = 'DESCRIBE applications_history'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #applications_notifications
    query = 'DESCRIBE applications_notifications'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #balancedcampuscalendar
    query = 'DESCRIBE balancedcampuscalendar'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

	#battery
    query = 'DESCRIBE battery'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

	#battery_charges
    query = 'DESCRIBE battery_charges'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #bluetooth
    query = 'DESCRIBE bluetooth'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #calls
    query = 'DESCRIBE calls'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #esms
    query = 'DESCRIBE esms'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #locations
    query = 'DESCRIBE locations'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #messages
    query = 'DESCRIBE messages'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_google_activity_recognition
    query = 'DESCRIBE plugin_google_activity_recognition'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_batterygauge
    query = 'DESCRIBE plugin_msband_sensors_batterygauge'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_calories
    query = 'DESCRIBE plugin_msband_sensors_calories'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_devicecontact
    query = 'DESCRIBE plugin_msband_sensors_devicecontact'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_distance
    query = 'DESCRIBE plugin_msband_sensors_distance'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_gsr
    query = 'DESCRIBE plugin_msband_sensors_gsr'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_heartrate
    query = 'DESCRIBE plugin_msband_sensors_heartrate'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_pedometer
    query = 'DESCRIBE plugin_msband_sensors_pedometer'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_skintemp
    query = 'DESCRIBE plugin_msband_sensors_skintemp'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_msband_sensors_uv
    query = 'DESCRIBE plugin_msband_sensors_uv'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #plugin_openweather
    query = 'DESCRIBE plugin_openweather'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #processor
    query = 'DESCRIBE processor'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #screen
    query = 'DESCRIBE screen'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    #wifi
    query = 'DESCRIBE wifi'
    data = make_query(cursor, query)
    queries = queries + [{"query": query, "results": data}]

    context = {"queries": queries}
    return template.render(context)

@app.route('/quality')
def quality():
    template = JINJA_ENVIRONMENT.get_template('templates/quality.html')
    return template.render()


# Takes the database link and the query as input
def make_query(cursor, query):
    # this is for debugging -- comment it out for speed
    # once everything is working

    try:
        # try to run the query
        cursor.execute(query)
        # and return the results
        return cursor.fetchall()
    
    except Exception:
        # if the query failed, log that fact
        logging.info("query making failed")
        logging.info(query)

        # finally, return an empty list of rows 
        return []

# helper function to make a query and print lots of 
# information about it. 
def make_and_print_query(cursor, query, description):
    logging.info(description)
    logging.info(query)
    
    rows = make_query(cursor, query)

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def application_error(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500

def bin_locations(locations, epsilon):
    # always add the first location to the bin
    bins = {1: [locations[0][0], locations[0][1]]}
    # this gives us the current maximum key used in our dictionary
    num_places = 1
    
    # now loop through all the locations 
    for location in locations:
        lat = location[0]
        lon = location[1]
        # assume that our current location is new for now (hasn't been found yet)
        place_found = False
        # loop through the bins 
        for place in bins.values():
            # check whether the distance is smaller than epsilon
            if distance_on_unit_sphere(lat, lon, place[0], place[1]) < epsilon:
                #(lat, lon) is near  (place[0], place[1]), so we can stop looping
                place_found = True
                    
        # we weren't near any of the places already in bins
        if place_found is False:
            logging.info("new place: {0}, {1}".format(lat, lon))
            # increment the number of places found and create a new entry in the 
            # dictionary for this place. Store the lat lon for comparison in the 
            # next round of the loop
            num_places = num_places + 1
            bins[num_places] = [lat, lon]

    return bins.values()
            
def find_bin(bins, lat, lon, epsilon):
    for i in range(len(bins)):
        blat = bins[i][0]
        blon = bins[i][1]
        if distance_on_unit_sphere(lat, lon, blat, blon) < epsilon:
            return i
    bins.append([lat, lon])
    return len(bins)-1

def group_activities_by_location(bins, locations, activities, epsilon):
    searchable_locations = {}
    for location in locations:
        # day, hour
        key = (location[0], location[1])
        if key in searchable_locations:
            # lat,   lon 
            searchable_locations[key] = locations[key] + [(location[2], location[3])]
        else:
            searchable_locations[key] = [(location[2], location[3])]
    
    # a place to store activities for which we couldn't find a location
    # (indicates an error in either our data or algorithm)
    no_loc = []
    for activity in activities:
        # collect the information we will need 
        aday = activity[0] # day
        ahour = activity[1] # hour
        aname = activity[2] # name
        logging.info(aday + aname)
        try: 
            possible_locations = searchable_locations[(aday, ahour)]
            # loop through the locations
            for location in possible_locations:
                logging.info(" about to find bin")
                bin = find_bin(bins, location[0], location[1], epsilon)
                # and add the information to it
                bins[bin] = bins[bin] + [aname]
        except KeyError:
            no_loc.append([aname])

    # add no_loc to the bins
    bins.append(no_loc)
    # this function is taken verbatim from http://www.johndcook.com/python_longitude_latitude.html

def distance_on_unit_sphere(lat1, long1, lat2, long2):

    # Convert latitude and longitude to 
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0
    
    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians
    
    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians
    
    # Compute spherical distance from spherical coordinates.
    
    # For two locations in spherical coordinates 
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) = 
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length
        
    cos = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) + 
           math.cos(phi1)*math.cos(phi2))
    # sometimes small errors add up, and acos will fail if cos > 1
    if cos>1: cos = 1
    arc = math.acos( cos )
    
    # Remember to multiply arc by the radius of the earth 
    # in your favorite set of units to get length.

#Method to group times in hours
def bin_times(times, theta):
    # always add the first time to the bin
    bins = {1: times[0]}
    
    # this gives us the current maximum key used in our dictionary
    num_places = 1
    
    # now loop through all the locations 
    for time in times:
        time = time
        # assume that our current location is new for now (hasn't been found yet)
        place_found = False
        # loop through the bins 
        for bin_time in bins.values():
            # check whether the distance is smaller than epsilon
            if gap_in_time(time, bin_time) < theta:
                #(lat, lon) is near  (place[0], place[1]), so we can stop looping
                place_found = True
                    
        # we weren't near any of the time already in bins
        if place_found is False:
            logging.info("new time:" + time[0])
            # increment the number of places found and create a new entry in the 
            # dictionary for this place. Store the lat lon for comparison in the 
            # next round of the loop
            num_places = num_places + 1
            bins[num_places] = time

    return bins.values()

#gap in time
def gap_in_time(ref_time, time):
    logging.info(ref_time[0])
    logging.info(time[0])
    FMT = '%H:%M'

    logging.info("Time difference")
    time_diff = datetime.strptime(ref_time[0], FMT) - datetime.strptime(time[0], FMT)
    logging.info("Time Difference: ")
    logging.info(time_diff)
    #works only for positive differences
    hours = time_diff.seconds//3600
    logging.info("Time Difference in hours: ")
    logging.info(hours)
    return hours

def group_activities_by_time(activities):
    time_tuples = {'0': [], '1': [], '2': [], '3': [], '4': [], '5': [], '6': [], '7': [], '8': [], '9': [], '10': [], '11': [], '12': [], '13': [], '14': [], '15': [], '16': [], '17': [], '18': [], '19': [], '20': [], '21': [], '22': [], '23': []}
    for activity in activities:
        # collect the information we will need 
        ahour = activity[0] # hour
        aname = activity[1] # name
        logging.info(ahour)
        logging.info(aname)
        FMT = '%H:%M'
        new_time = datetime.strptime(ahour, FMT)
        hours = str(new_time.hour)
        logging.info(hours)
        try:
        	if time_tuples.get(hours) == None:
	        	logging.info("None")
	        else:
	        	logging.info("Something")
	        	activity_array = time_tuples.get(hours)
	        	activity_array.append(aname)
        except KeyError:
	    	
	    	pass
    #time_tuples = {'00:00': activities[0]}
    logging.info(time_tuples)
    return time_tuples

