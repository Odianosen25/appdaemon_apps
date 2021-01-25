AN App Daemon App that helps to create a dashbaord, which can be used to debug service calls.

To install it do the following:
- Download the dev_tools folder and place them in your apps directory
- Then move the `dev_tool.dash` file, and put in your dashbaord directory

The app uses the `default` directory to function, as its assumed that is where most users have as their Hass namespace
If that is not your case, then I wil need to upload other files to allow it work as I don't use the Hass plugin namespace

To make a service call do the following:
- Select the namespace you want to execute the service call
- Then select the service call to be made
- Enter the keyworded args needed in the call, separated with a `,` for example `entity_id=light.living_room, brightness=100`
