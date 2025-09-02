## About

A simple setup to limit childs screentime on a (typically windows) computer.

It sets up a daily screentime limit and adds for allowing more time upon request.

Very basic. Compared to microsoft family safety, it has these advantages:

* Easier to set up
* Independent on cloud, all is fully local
* Works offline


## Setup

1. Child needs to have a non-admin account.
2. On the admin account, you put the monitor.py script to some folder that is not visible from childs account.
3. The monitor.py script is run from python upon machine startup
4. Current version of the script assumes Windows Pro (on Home, the "msg" doesn't work)

## Safety

Make sure to password-protect biols to prevent boot from other device.
Encrypt the hard-drive by bitlocker to prevent the child physically taking out the hard drive and modifying some system files from elsewhere.

## Extra time request

If you want to grant extra time to the child, you generate a code that looks like this `<date>:<extra_time_seconds>:<signature>` where
* date is in format YYYY-MM-DD
* extra time is an integer
* signature is 4 or more characters
A typical code can look like 2025-09-02:3600:a184 which would grant an extra hour (3600 seconds) valid during the date.

The child writes this code to the file specified int monitor.py text document.

To generate the codes, the parent can run the create_code.py script on his machine.
Both machines share a secret password which should not be shared with the child.


## Python dependencies

None!