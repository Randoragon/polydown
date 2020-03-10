#!/usr/bin/env python3

import socket
import sys
import re
from datetime import datetime, timedelta, date as dt_date, time as dt_time

PORT = 5000

ACTION = {
        'add'   : 0,
        'ls'    : 1,
        'list'  : 1,
        'rm'    : 2,
        'pidof' : 3,
        'index' : 4,
        'cat'   : 5,
        'cmd'   : 6,
        'stat'  : 7,
        'kill'  : 8
}

OBJECT = {
        'timer'     : 0,
        'alarm'     : 1,
        'stopwatch' : 2,
        'counter'   : 3
}

def send(msg):
    '''Sends a string as-is to the server'''
    if msg is None:
        return False
    try:
        print(f'Sending: "{msg}"')
        host = socket.gethostname()
        client_socket = socket.socket()
        client_socket.connect((host, PORT))
        client_socket.send(str(msg).encode())
        data = client_socket.recv(1024).decode()
        if len(data) != 0:
            print(re.sub(r'\\n', '\n', data))
        client_socket.close()
    except ConnectionRefusedError:
        print('Error: Connection to server failed')
    except Exception as e:
        print(f'Error: Unprecedented exception caught:\n  {type(e).__name__}')
    return True

def convert(msg):
    '''Converts raw user input into precise information for the server'''

    # Matches natural numbers and counter names
    REGEX = r'^([0-9]+)|(@[\w]+)$'  

    # Aliases for cleaner code 
    A = ACTION 
    ERR_PID_NAME   = '\'{}\' is neither a PID nor a counter name, aborting...'
    ERR_INDEX_NAME = '\'{}\' is neither an index nor a counter name, aborting...'

    # Split arguments
    msg = msg.split()

    # If no action specified, infer add
    if msg[0] not in A:
        msg.insert(0, 'add')

    # Process specific actions
    action = A[msg[0]]
    if action in (A['ls'], A['kill']):
        if len(msg) > 1:
            print(f'\'{msg[0]}\' does not take parameters, ignoring...')
        ret = str(action)
    elif action in (A['rm'], A['pidof'], A['index'], A['cmd'], A['cat'], A['stat']):
        for i in msg[1:]:
            if not re.match(REGEX, i):
                print(ERR_INDEX_NAME.format(i) if action != A['index'] else ERR_PID_NAME.format(i))
                ret = None
        ret = ' '.join((str(action), *msg[1:]))
    elif action == A['add']:
        ERR_MSG = 'Failed to parse parameters, aborting...'

        # Cache these values
        msg = msg[1:]
        string = ' '.join(msg)

        # These will hold final data that will be passed to the send() function
        obj, arg = None, None

        # Timer
        if all(is_time_chunk(i) for i in msg):
            obj = OBJECT['timer']
            arg = str(sum(list(time_chunk_to_sec(i) for i in msg)))

        # Alarm (time chunk format)
        elif string[0] == '+':
            obj = OBJECT['alarm']
            # Trim the + sign to leave out only time chunks
            if msg[0] == '+':
                del msg[0]
            else:
                msg[0] = msg[0][1:]
            if any(not is_time_chunk(i) for i in msg):
                print('Error: Invalid alarm parameters')
                ret = None
            else:
                arg = str(sum(list(time_chunk_to_sec(i) for i in msg)))

        # Stopwatch
        elif msg[0] == 's':
            obj = OBJECT['stopwatch']
            del msg[0]
            if any(not is_time_chunk(i) for i in msg):
                print('Error: Invalid stopwatch parameters')
                ret = None
            else:
                arg = str(sum(list(time_chunk_to_sec(i) for i in msg)))

        # Counter
        elif msg[0] == 'c':
            obj = OBJECT['counter']
            if len(msg) < 2:
                print('Error: Not enough arguments for counter')
                ret = None
            elif re.match(r'^(\d+|@\w+)$', msg[1]) is None:
                print('Error: invalid counter index/name')
                ret = None
            else:
                del msg[0]
                # If only name is passed, value becomes 0 by default
                if len(msg) == 1:
                    arg = f'{msg[0]} 0'
                # If value was passed without an operand (set value)
                elif len(msg) == 2 and re.match(r'^\d+(\.\d+)?$', msg[1]):
                    arg = f'{msg[0]} {msg[1]}'
                # if operator was passed with a space before the operand (e.g. + 5)
                elif len(msg) == 3 and msg[1] in ('+', '-', '*', '/', '%', '^') and re.match(r'^\d+(\.\d+)?$', msg[2]):
                    # modulo is only allowed with integers
                    if msg[1] == '%' and '.' in msg[2]:
                        print('Error: operation modulo (%) is only allowed with integer parameters!')
                        ret = None
                    arg = ' '.join(msg)
                # if operator and operand were passed as one parameter (e.g. +5)
                elif len(msg) == 2 and msg[1][0] in ('+', '-', '*', '/', '%', '^') and re.match(r'^\d+(\.\d+)?$', msg[1][1:]):
                    arg = ' '.join((msg[0], msg[1][0], msg[1][1:]))

        # Alarm again (datetime format)
        else:
            dt = extract_datetime(string)
            if dt is not None:
                obj = OBJECT['alarm']
                arg = '{}-{}-{} {}:{}:{}'.format(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            else:
                print('Error: Invalid syntax')
                ret = None

        if action is None or obj is None or arg is None:
            ret = None
        else:
            ret = ' '.join(tuple(map(str, (action, obj, arg))))
    return ret

def is_time_chunk(s):
    '''A "time chunk" is a string in this format: 5s, 3d, 0.3s...'''
    return re.match(r'^[\d]+(\.\d+[smhd]|[smhd]?)$', s) is not None

def time_chunk_to_sec(s):
    if s[-1] not in ('s', 'm', 'h', 'd') and '.' not in s:
        return float(s)
    if s[-1] == 's':
        return float(s[:-1])
    if s[-1] == 'm':
        return 60 * float(s[:-1])
    if s[-1] == 'h':
        return 3600 * float(s[:-1])
    if s[-1] == 'd':
        return 86400 * float(s[:-1])
    raise ValueError(f'\'{s}\' is not a time chunk!')

def extract_datetime(s):
    '''Converts a datetime string into a datetime object'''
    now = datetime.now()
    args = s.upper().split()

    if len(args) == 1:
        # This is a good way to check if a single parameter is time,
        # because standalone time always has one of these substrings.
        # Careful though! If time is preceded by date, it's possible
        # to omit the colon for 24-hour time strings (e.g. "pdc 3/2 15").
        if ':' in args[0] or 'PM' in args[0] or 'AM' in args[0]:
            time = args[0]
            date = None
        else:
            time = None
            date = args[0]
    elif len(args) == 2:
        date, time = args
    else:
        print('Too many arguments. See "pdc --help" for reference.')
        return None

    day,  month,  year   = (None,) * 3
    hour, minute, second = (None,) * 3
    pm_am = None

    if date is not None:

        # Extract date
        match = re.match(r'^(?P<day>\d+)\.(?P<month>\d+)(\.(?P<year>\d+))?$', date)
        if match is None:
            match = re.match(r'^(?P<month>\d+)/(?P<day>\d+)(/(?P<year>\d+))?$', date)
            if match is None:
                match = re.match(r'^(?P<year>\d+)-(?P<month>\d+)(-(?P<day>\d+))?$', date)
                if match is None:
                    print('Unrecognized date format. Available: "dd.mm.yyyy", "mm/dd/yyyy", "yyyy-mm-dd"')
                    return None
        # Notice that in the first two formats year can be omitted,
        # while in the third format the day can be omitted.
        # If a day is omitted, we simply assume it to be 1.
        # If a year is omitted however, we have to pick the lowest possible
        # year for the rest of the datetime to make sense,
        # i.e. if it is currently August and the user request a date
        # in November, the year is assumed to be the current one,
        # but if the requested a date in March, the year would have to be
        # the subsequent one. The check will be performed later.

        # Store matches
        day   = match.group('day'  )
        month = match.group('month')
        year  = match.group('year' ) 
 
        # Convert known values
        day   = int(day if day is not None else 1)
        month = int(month)
        year  = int(year) if year is not None else None

    # If date is omitted completely and there's only time,
    # then depending on the current time the date will either be
    # today or tomorrow. This check is also performed later.
    
    if time is not None:
        # Extract time
        # Some match strings contain unmatchable groups, e.g. '...$(?P<unmatchable>_)?'
        # This is a hacky way to enforce that these named groups always exist in the match object,
        # to avoid ugly checks later on. Basically, everything that doesn't exist always has None value.
        match = re.match(r'^(?P<hour>\d+):(?P<minute>\d+)(:(?P<second>\d+))?$(?P<pm_am>_)?', time)
        if match is None:
            match = re.match(r'^(?P<hour>\d+)(:(?P<minute>\d+)(:(?P<second>\d+))?)?(?P<pm_am>PM|AM)', time)
            if match is None and date is not None:
                match = re.match(r'^(?P<hour>\d+)$(?P<minute>_)?(?P<second>_)?(?P<pm_am>_)?', time)
                if match is None:
                    print('Unrecognized time format. See "pdc --help" for valid examples.')
                    return None

        # Store matches
        hour   = match.group('hour'  )
        minute = match.group('minute')
        second = match.group('second')
        pm_am  = match.group('pm_am' )

    # Convert to int and if any time values were omitted, assume 0
    hour   = int(hour   if hour   is not None else 0)
    minute = int(minute if minute is not None else 0)
    second = int(second if second is not None else 0)

    # Verify time validity
    try:
        dt = dt_time(hour, minute, second)
    except Exception as e:
        print(f'{type(e).__name__}: {e}')
        return None

    # Convert 12-hour time to 24-hour time
    if pm_am is not None:
        if hour == 12 and pm_am == 'AM':
            hour = 0
        elif hour != 12 and pm_am == 'PM':
            hour += 12
    
    # If date was omitted, find the closest suitable one
    if date is None:
        d = datetime(now.year, now.month, now.day, hour, minute, second)
        if d < now:
            d += timedelta(1)
        day   = d.day
        month = d.month
        year  = d.year

    # If year was omitted, find the closest suitable one
    elif year is None:
        # Verify month and day validity
        # Use 2016 as year, because it was a leap year (Feb 29 is a valid date)
        try:
            dt = dt_date(2016, month, day)
        except Exception as e:
            print(f'{type(e).__name__}: {e}')
            return None

        # Increment year till the date is valid and in the future
        year = now.year
        dt = datetime(year, month, day, hour, minute, second)
        while dt < now:
            year += 1
            try:
                dt = datetime(year, month, day, hour, minute, second)
            except ValueError:
                continue

    # Verify full timedate validity
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except Exception as e:
        print(f'{type(e).__name__}: {e}')
        return None
    
    return dt

if __name__ == '__main__':
    if len(sys.argv) == 1:
        send(ACTION['list'])
    elif sys.argv[1] in ('--help', '-h'):
        print('''PDC(1)

NAME
        pdc - polydown client

SYNOPSIS
        pdc [OPTIONS] [ACTION] [VALUE] [-- COMMAND]

DESCRIPTION
        PDC is a command-line client for the Polydown server (polydown).
        It connects to the server and sends messages to control its actions.

        Polydown is a great tool for setting up quick timers, alarms,
        executing commands at the end of countdowns, setting up counters...

OPTIONS
        -p <PORT>, --port <PORT>
        The port the server is listening on, default is 5000.

        -h, --help
        Print this help page.

        -i <FILE>, --input <FILE>
        Run pdc for every line in file, using each line as parameters.

        -c <BEGIN:END> <FG:BG>
        When object's value within the given range, set its foreground
        and background color to a hex value. This option can be passed
        multiple times to specify different ranges. Also, you can omit
        either BEGIN, END or both to specify a limitless range.
        You can omit FG or BG to reset that color to polybar default.
        Don't forget the colons, even if omitting some values.

        -f <INDEX>... [BEGIN:END], --format <INDEX>... [BEGIN:END]
        Print a polybar-formatted string including all objects whose
        indices were listed. Formatting includes BG and FG colors for
        each object that was created with the -c option.
        You may use a colon range to specify a range of indices
        (same rules as in -c, e.g. use a single colon to list all).
        If this option is used, no ACTION can follow, every subsequent
        parameter is interpreted as an object index.
        This is the intended option to use in a Polybar config
        as custom/script type.

ACTIONS
        add [@LABEL] <EXPRESSION>
            The default action (you can omit add for the same effect).
            Creates a new time object and returns its index and PID.
            @LABEL is an optional alphanumeric string (a-z A-Z 0-9 _).
            When using the --format option, the label text will be put
            next to an object's value. Labels are also interchangeable
            with object indices in most commands, hence the "@" prefix
            for easy distinction between the two. Multiple objects may
            have the same label, in which case a command affects every
            object in possession of that label.
            EXPRESSION is a list of parameters defining a time object
            to be created/changed. See "TIME OBJECTS SYNTAX" section.

        rm [INDEX]... [@LABEL]...
            Permanently removes an existing time object. Works with
            any number of space-separated indices/labels. To destroy
            all objects at once, you may use a single asterisk (*).

        ls, list
            Lists all existing time objects with basic information.
            Calling "pdc" with no arguments defaults to this action.

        pidof [INDEX]... [@LABEL]...
            Prints PIDs of all objects matching the indices/labels.

        index [PID]... [@LABEL]...
            Prints indices of all objects matching the PIDs/labels.

        cmd [INDEX]... [@LABEL]...
            Prints commands of all objects matching the indices/labels.
            Objects without commands are ignored in the output.

        cat [INDEX]... [@LABEL]...
            Prints values of all objects matching the indices/labels.
            The output for different time object types will be:
                * timers:      remaining time
                * alarms:      alarm datetime
                * stopwatches: elapsed time
                * counters:    current value

        stat [INDEX]... [@LABEL]...
            Prints every known information about all objects matching
            the indices/labels. The information respectively includes:
                * always:      type, index, PID, label
                * timers:      starting and remaining time, command
                * alarms:      alarm datetime, remaining time, command
                * stopwatches: starting and elapsed time
                * counters:    stored value
            
        kill
            Kills the Polydown server. This is exactly the same as calling
            "polydown -k" or "polydown --kill". All existing time objects
            will be saved and readded upon restarting the server.


TIME OBJECTS SYNTAX

------- TIMER - counts down a specified amount of time.

        Syntax:
            pdc [CHUNK]... [-- COMMAND]
            A time "chunk" is a real number followed by a time unit.
            Available units are: d, h, m, s (day, hour, minute, second).
            The timer will be set to the sum of all time chunks.
            Optionally, you can include a COMMAND string which will be
            executed once the timer hits 0.

        Examples:
            pdc 5           - set to 5 seconds (default unit)
            pdc 1h 2m 3s    - set to 1 hour, 2 minutes and 3 seconds
            pdc 2m 1d 5s    - set to 1 day, 2 minutes and 5 seconds
            pdc 2.5h 4 4    - set to 2 hours, 30 minutes and 8 seconds

------- ALARM - calculates time difference between some point in time
        and the present.

        Syntax:
         1) pdc [dd.mm.yyyy] [HH:MM:SS] [pm/am] [-- COMMAND]
            pdc [mm/dd/yyyy] [HH:MM:SS] [pm/am] [-- COMMAND]
            pdc [yyyy-mm-dd] [HH:MM:SS] [pm/am] [-- COMMAND]
            You may omit many parameters as long as it's unambiguous.
            If no pm/am specification, 24-hour time is inferred.

         2) pdc +[CHUNK]... [-- COMMAND]
            Same principle as with timers, but note the "+" prefix.
            Think of it as "set an alarm THIS far into the future".
            Unlike a timer, the time will be rounded to full seconds.

            Optionally, you can include a COMMAND string which will be
            executed once the alarm hits 0. The command will be ignored
            if the specified time goes by while the server is down.

        Examples:
            pdc 5pm                  - set to the closest 5pm
            pdc 17:00                - same as above
            pdc 25.06 13:15          - set to Jun 25th, 13:15
            pdc 12/23/2055 7:30:15am - set to Dec 23rd 2055, 7:30:15am
            pdc 1.2                  - set to the closest Feb 1st
            pdc 5/3 8                - set to 8am on May 3rd 
            pdc +12m 180s            - set to 15 minutes from now

------- STOPWATCH - measures time like a stopwatch (in miliseconds)

        Syntax:
            pdc s [CHUNK]...
            The syntax for CHUNK works exactly the same as for timers.
            The sum of all chunks will be used as the initial state.

        Examples:
            pdc s       - starts from 0 (default)
            pdc s 100   - starts from 100 seconds
            pdc s 1h 3m - starts from 1 hour and 3 minutes

------- COUNTER - stores a number and lets you transform it at will

        Syntax:
            pdc c <TARGET> [OPERATOR] [VALUE]
            TARGET must be either INDEX or @LABEL (note the prefix).
            OPERATOR must be one of: +, -, *, /, //, ^, %
            VALUE must be a real number, display precision is 0.001.

            When specifying TARGET by index, if the index does not
            belong to a counter object, you will receive a warning.

        Examples:
            pdc c 0         - create a new counter and set to 0
            pdc c 2 +1      - add 1 to the counter with index 2
            pdc c 4 ^-0.12  - raise index 4 to the -0.12th power
            pdc c 1 %4      - set index 1 to its value mod 4
            pdc c @abc 0    - set counters with "abc" label to 0


IMPORTANT NOTES
        1) Timer and Alarm - What\'s the difference?
            Consider the following example:
            pdc 10m
            pdc +10m
            After running the above two lines, if you shut down your
            computer and rebooted after 5 minutes, the timer would
            still be at 10 minutes, but an alarm would already be at 5,
            because it remembers a point in time rather than time left.
        
        2) Datetime vs Time Amounts
            Let these examples be a disambiguation of certain behavior:
            pdc 5     - add a timer and set to 5 seconds
            pdc 4.5   - add an alarm for May the 4th
            pdc 4.5s  - add a timer and set to 4.5 seconds

            As you can see, the "s" suffix for timers is optional when
            dealing with integers, but is required for fractions to
            differentiate between dates and time amounts. 


        3) Midnights, starts and ends of days
            All these datetimes denote the start of the 8th of March:
            pdc 8.3
            pdc 8.3 00:00
            pdc 8.3 0
            pdc 8.3 12:00am
            pdc 8.3 12am

        4) Fractions and precision
            You may use fractions for timers and alarms, but beware:
            * Timers remember the time left in miliseconds (0.001s)
            * Alarms remember a datetime only up to full seconds

            Comparison:
            "pdc 4.2312h" will evaluate to 4.23279*3600 =~ 15238.044s
            "pdc +4.2312h" will set an alarm to 15238s from now.


Thank you for using polydown!

Source code: https://github.com/Randoragon/polydown

Copyright (C) 2020 Randoragon. Distributed under the MIT License.''')
    else:
        send(convert(sys.argv[1:]))
