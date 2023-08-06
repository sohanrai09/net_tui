### Introduction

Goal of this little project was me to explore the amazing [Textual](https://textual.textualize.io/) library.
In this project, I'm building an `app` in the terminal using `Textual` to perform some basic networking related tasks. I've used [Nornir](https://nornir.readthedocs.io/en/latest/)
to do the underlying networking tasks.

As of now, `net_tui` has the functions.
1. To build a Dashboard with some system and routing protocol information.
2. To look up a card in a given list of devices.
3. To look up any pattern of configuration in a list of devices.
4. To fetch the output of any command across a list of devices.
5. To generate CLI commands as per the current running configuration on the device, with an option of terse and verbose levels.

For now, list of cards and commands used in function 2 and 4 respectively have been defined manually. May be in the future I can think of making this a
bit more dynamic.

Note: This only works on Juniper devices.

### `net_tui` in action

https://github.com/sohanrai09/net_tui/assets/89385413/38decade-628d-4414-91ac-6b748ee37be4

### Reference

- [net-textorial](https://github.com/dannywade/net-textorial) by Danny Wade. Danny talks about his project on his [Youtube Channel](https://www.youtube.com/watch?v=H8uGOIK2ZqY), highly recommend following him.

- [Textual](https://textual.textualize.io/) has a very robust documentation, and they are always adding things to it to make it easier to explore.
