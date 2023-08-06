from nornir import InitNornir
from nornir_pyez.plugins.tasks import pyez_rpc
from nornir_pyez.plugins.tasks import pyez_facts
from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.widgets import Header, Footer, Input, Static, Button, Label, TabbedContent, TabPane, LoadingIndicator, \
    RadioSet, RadioButton
from rich.syntax import Syntax
from rich.console import Console
from nornir_napalm.plugins.tasks import napalm_cli
from textual_autocomplete import AutoComplete, Dropdown, DropdownItem
from textual.screen import ModalScreen
import re
import datetime
import yaml
import pyperclip
from rich.table import Table
from rich import box
from nornir.core.task import Task, Result
from textual import work

today = datetime.date.today()
console = Console()

nr = InitNornir(config_file='norn_inv/config.yaml')
nr_hosts = nr.inventory.hosts
hosts_list = []
for host in nr_hosts.keys():
    hosts_list.append(DropdownItem(host))

with open('card_inventory.txt', 'r') as f:
    card_inv = f.readlines()

with open('cli_commands.txt', 'r') as f:
    cli_inv = f.readlines()

cards = []
cli_cmds = []

for card in card_inv:
    cards.append(DropdownItem(card.strip()))

for cli in cli_inv:
    cli_cmds.append(DropdownItem(cli.strip()))


def protocol_list(nornir_obj, device_name):
    cfg_result = nornir_obj.run(task=napalm_cli, commands=['show configuration | display set'])
    cfg_output = cfg_result[device_name][0].result['show configuration | display set']
    protocols = re.findall(".*protocols (\w+).*", cfg_output)
    unique_protocols = list(set(protocols))
    return unique_protocols


class QuitScreen(ModalScreen):
    """Screen with a dialog to quit."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
        else:
            self.app.pop_screen()


def main_task(task: Task):
    """
    Nornir task which groups together all the individual tasks and
    returns Aggregated result
    """
    task.run(name='facts', task=pyez_facts)
    task.run(name='alarms', task=pyez_rpc, func='get-system-alarm-information')
    task.run(name='rib_fib', task=pyez_rpc, func='get-route-summary-information')
    task.run(name='memory', task=pyez_rpc, func='get-system-memory-information')
    task.run(name='cpu', task=pyez_rpc, func='get-route-engine-information')
    task.run(name='commit', task=pyez_rpc, func='get-commit-information')
    return Result(host=task.host)


class NetTUI(App):
    """A Textual app to manage stopwatches."""

    CSS_PATH = "my_app.css"

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
                ("c", "copy_cmds", "Copy to clipboard"),
                ("f", "fetch_output", "Fetch output"),
                ("q", "request_quit", "Quit")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""

        yield Header()

        with TabbedContent(initial="dash"):
            with TabPane("Dashboard", id="dash"):
                yield Container(
                    AutoComplete(Input(
                        placeholder="Device Name", id="device_name"),
                        Dropdown(items=hosts_list, id='host_dropdown')),
                    Button(label="Build Dashboard", variant="primary", id="button1"),
                    id="input_container")

                yield LoadingIndicator(id='load1')
                yield Container(Static(id="static1_1"), id='container1')

            with TabPane("Checker", id='check'):
                yield LoadingIndicator(id='load2')
                yield Container(
                    AutoComplete(Input(
                        placeholder="Enter the card name to lookup",
                        id="card_name"),
                        Dropdown(items=cards, id='card_dropdown')),

                    Button(label="Clear!", variant="primary", id="clear_button"),
                    id="card_container")

                yield Container(Input(
                    placeholder="Search the configs for :",
                    id="cfg"),

                    Button(label="Search!", variant="primary", id="search_button"),
                    id="cfg_container",
                )

                yield Container(AutoComplete(Input(
                    placeholder="Fetch output of commands from all devices :",
                    id="cmds"),
                    Dropdown(items=cli_cmds, id='cli_dropdown')),

                    Button(label="Fetch!", variant="primary", id="fetch_button"),
                    id="cmd_container",
                )

                yield Static(id='out')

            with TabPane("Generator", id='gen'):
                yield Container(AutoComplete(Input(placeholder="Enter the device name to generate checks",
                                                   id="device_name2"), Dropdown(items=hosts_list, id='host_dropdown2')),

                                id="input_container2")
                yield Container(RadioSet(RadioButton("terse", value=True),
                                         RadioButton("verbose"), id='default'),
                                Button(label="generate", variant="primary", id="generate"), id='button_container2')

                yield LoadingIndicator(id='load3')
                yield Static(id='gen_out')

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        # Give the input focus, so we can start typing straight away
        self.query_one("#device_name").focus()
        # Disabling the loading indicators to start with
        self.query_one('#load1').display = False
        self.query_one('#load2').display = False
        self.query_one('#load3').display = False

    def action_request_quit(self) -> None:
        self.push_screen(QuitScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:

        """Run when user clicks a button"""
        if event.button.id == 'button1':
            device_name = self.query_one("#device_name")
            self.dasbboard_build(device_name.value)
        elif event.button.id == 'clear_button':
            self.query_one("#card_name").action_delete_left_all()
            self.query_one("#cfg").action_delete_left_all()
            self.query_one("#cmds").action_delete_left_all()
            self.query_one("#out", Static).update('')
        elif event.button.id == 'search_button':
            cfg_src = self.query_one("#cfg")
            if cfg_src.value:
                self.cfg_fetch(cfg_src.value)
        elif event.button.id == 'fetch_button':
            cmds = self.query_one("#cmds")
            if cmds.value:
                self.cmd_fetch(cmds.value)
        elif event.button.id == 'generate':
            device_name = self.query_one("#device_name2")
            if self.query_one(RadioSet).pressed_index == 0:
                self.checks_generate(device_name.value, 'terse')
            elif self.query_one(RadioSet).pressed_index == 1:
                self.checks_generate(device_name.value, 'verbose')

    @work
    def dasbboard_build(self, device_name):
        self.query_one("#static1_1", Static).update('')
        self.query_one('#load1').display = True
        new_nr = nr.filter(site=device_name)
        main_result = new_nr.run(task=main_task)
        facts_data = main_result[device_name][1].result
        version = facts_data.get('version')
        model = facts_data.get('model')
        serial_num = facts_data.get('serialnumber')
        re0 = facts_data.get('RE0')
        re1 = facts_data.get('RE1')  # Returns None if RE1 is not present
        if re0:
            re0_uptime = re0.get('up_time')
            re0_last_reboot_reason = re0.get('last_reboot_reason')
        else:
            re0_uptime = 'NA'
            re0_last_reboot_reason = 'NA'
        if re1:
            re1_uptime = re1.get('up_time')
            re1_last_reboot_reason = re1.get('last_reboot_reason')
        else:
            re1_uptime = 'NA'
            re1_last_reboot_reason = 'NA'
        # Extracting active alarms information
        alarms_data = main_result[device_name][2].result
        alarms_list_final = []
        try:
            alarms_var = alarms_data.get('alarm-information')['alarm-detail']
            if isinstance(alarms_var, list):
                for alarm in alarms_var:
                    alarms_list_final.append(alarm['alarm-description'])
            else:
                alarms_list_final.append(alarms_var['alarm-description'])
        except KeyError:
            alarms_list_final.append("None")

        sys_info_table = Table(show_lines=True, show_header=False, box=box.ASCII, title='System Information')
        sys_info_table.add_column("Field", justify="right", style="magenta", width=18)
        sys_info_table.add_column("Details", style="cyan", width=50)
        sys_info_table.add_row('SW version', version)
        sys_info_table.add_row('Model', model)
        sys_info_table.add_row('Serial Number', serial_num)
        sys_info_table.add_row('RE0 uptime', re0_uptime)
        sys_info_table.add_row('RE0 last reboot reason', re0_last_reboot_reason)
        sys_info_table.add_row('RE1 uptime', re1_uptime)
        sys_info_table.add_row('RE1 last reload reason', re1_last_reboot_reason)

        for alarm in alarms_list_final:
            sys_info_table.add_row('Active alarms', alarm)

        # Extracting CPU and memory info
        used_value, free_value, cpu_usage_list = [], [], [],
        memory_data = main_result[device_name][4].result
        free_mem = memory_data['system-memory-information']['system-memory-summary-information'][
            'system-memory-free-percent']
        free_mem_int = int(re.sub('%', '', free_mem))
        used_mem = 100 - free_mem_int
        used_value.append(used_mem)
        free_value.append(free_mem_int)

        cpu_data = main_result[device_name][5].result
        cpu_check = cpu_data['route-engine-information']['route-engine']
        if isinstance(cpu_check, dict):  # This means device is having single RE
            cpu_usage = cpu_data['route-engine-information']['route-engine']['cpu-user']
            cpu_usage_list.append(int(cpu_usage))
        elif isinstance(cpu_check, list):  # This means device is having dual REs
            cpu_usage = cpu_data['route-engine-information']['route-engine'][0]['cpu-user']
            cpu_usage_list.append(int(cpu_usage))

        mem_cpu_table = Table(show_header=False, box=box.ASCII, width=50, title='Memory & CPU Information')
        mem_cpu_table.add_column("Field", justify="left", style="magenta")
        mem_cpu_table.add_column("Values", justify="left", style="cyan")
        mem_cpu_table.add_row("[cyan]CPU in use[/cyan]", f"[green]{str(cpu_usage)}%")
        mem_cpu_table.add_row("[cyan]\nMemory in use[/cyan]", f"\n[green]{str(used_mem)}%")

        # Extracting commit info
        commit_data = main_result[device_name][6].result
        commit_user = commit_data['commit-information']['commit-history'][0]['user']
        commit_time = commit_data['commit-information']['commit-history'][0]['date-time']['#text']

        commit_table = Table(show_header=False, box=box.ASCII, width=50, title='Commit Information', style="blue")
        commit_table.add_column("Field", justify="left")
        commit_table.add_row("[cyan]Last commit by [/cyan]", f"[green]{commit_user}")
        commit_table.add_row("[cyan]\nLast commit at [/cyan]", f"\n[green]{commit_time}")

        mem_cpu_commit_table = Table(show_header=False, box=box.ASCII, width=53, show_edge=False)
        mem_cpu_commit_table.add_column("Field", justify="left", style="magenta")
        mem_cpu_commit_table.add_row(mem_cpu_table)
        mem_cpu_commit_table.add_row("\n")
        mem_cpu_commit_table.add_row(commit_table)

        # Extracting routing Protocols Info
        protocols_table = Table(show_lines=True, show_header=False, box=box.ASCII, width=47,
                                title='Protocol Information')
        protocols_table.add_column("Field", justify="right", style="magenta")
        protocols_table.add_column("Details", style="cyan")
        protocols = protocol_list(new_nr, device_name)
        if 'bgp' in protocols:
            bgp_result = new_nr.run(name='bgp', task=pyez_rpc, func='get-bgp-summary-information')
            bgp_data = bgp_result[device_name][0].result
            total_peers = bgp_data['bgp-information']['peer-count']
            down_peers = bgp_data['bgp-information']['down-peer-count']
            protocols_table.add_row("BGP Peer UP count", str(int(total_peers) - int(down_peers)))
            protocols_table.add_row("[yellow]BGP Peer DOWN count", down_peers)
        if 'isis' in protocols:
            isis_result = new_nr.run(name='isis', task=pyez_rpc, func='get-isis-adjacency-information')
            isis_data = isis_result[device_name][0].result
            adj_up_count = 0
            adj_down_count = 0
            isis_list = isis_data['isis-adjacency-information']['isis-adjacency']
            if isinstance(isis_list, list):
                for adj in isis_list:
                    if adj.get('adjacency-state') == 'Up':
                        adj_up_count = adj_up_count + 1
                    else:
                        adj_down_count = adj_down_count + 1
            else:
                if isis_list['adjacency-state'] == 'Up':
                    adj_up_count = adj_up_count + 1
                else:
                    adj_down_count = adj_down_count + 1
            protocols_table.add_row("ISIS Adj UP count", str(adj_up_count))
            protocols_table.add_row("[yellow]ISIS Adj DOWN count", str(adj_down_count))
        if 'ospf' in protocols:
            ospf_result = new_nr.run(name='ospf', task=pyez_rpc, func='get-ospf-neighbor-information')
            ospf_data = ospf_result[device_name][0].result
            ospf_full_count = 0
            ospf_down_count = 0
            ospf_nbr_list = ospf_data['ospf-neighbor-information']['ospf-neighbor']
            if isinstance(ospf_nbr_list, list):
                for nbr in ospf_nbr_list:
                    if nbr.get('ospf-neighbor-state') == 'Full':
                        ospf_full_count = ospf_full_count + 1
                    else:
                        ospf_down_count = ospf_down_count + 1
            else:
                if ospf_nbr_list['ospf-neighbor-state'] == 'Full':
                    ospf_full_count = ospf_full_count + 1
                else:
                    ospf_down_count = ospf_down_count + 1
            protocols_table.add_row("OSPF Nbr UP/Full count", str(ospf_full_count))
            protocols_table.add_row("[yellow]OSPF Nbr DOWN count", str(ospf_down_count))
        if 'mpls' in protocols:
            mpls_result = new_nr.run(name='mpls', task=pyez_rpc, func='get-mpls-lsp-information')
            mpls_data = mpls_result[device_name][0].result
            lsp_data = mpls_data['mpls-lsp-information']['rsvp-session-data']
            lsp_up_dict = {}
            lsp_down_dict = {}
            for lsp_type in lsp_data:
                lsp_up_dict[lsp_type['session-type']] = lsp_type['up-count']
                lsp_down_dict[lsp_type['session-type']] = lsp_type['down-count']
            protocols_table.add_row("MPLS Ingress LSP UP count", str(lsp_up_dict['Ingress']))
            protocols_table.add_row("[yellow]MPLS Ingress LSP DOWN count", str(lsp_down_dict['Ingress']))
            protocols_table.add_row("MPLS Egress LSP UP count", str(lsp_up_dict['Egress']))
            protocols_table.add_row("[yellow]MPLS Egress LSP DOWN count", str(lsp_down_dict['Egress']))
            protocols_table.add_row("MPLS Transit LSP UP count", str(lsp_up_dict['Transit']))
            protocols_table.add_row("[yellow]MPLS Transit LSP DOWN count", str(lsp_down_dict['Transit']))
        if 'ldp' in protocols:
            ldp_result = new_nr.run(name='ldp', task=pyez_rpc, func='get-ldp-session-information')
            ldp_data = ldp_result[device_name][0].result
            ldp_session = ldp_data['ldp-session-information']['ldp-session']
            ldp_up_count = 0
            ldp_down_count = 0
            if isinstance(ldp_session, list):
                for ldp_nbr in ldp_session:
                    if ldp_nbr.get('ldp-session-state') == 'Operational':
                        ldp_up_count = ldp_up_count + 1
                    else:
                        ldp_down_count = ldp_down_count + 1
            else:
                if ldp_session.get('ldp-session-state') == 'Operational':
                    ldp_up_count = ldp_up_count + 1
                else:
                    ldp_down_count = ldp_down_count + 1
            protocols_table.add_row("LDP Session Operational count", str(ldp_up_count))
            protocols_table.add_row("[yellow]LDP Session Non-Operational count", str(ldp_down_count))
        # Extracting route information
        route_data = main_result[device_name][3].result
        # rib_count = route_data['route-summary-information']['routing-highwatermark']['rt-all-highwatermark']
        # fib_count = route_data['route-summary-information']['routing-highwatermark']['rt-fib-highwatermark']
        # protocols_table.add_row("RIB routes", rib_count)
        # protocols_table.add_row("FIB routes", fib_count)
        main_table = Table(show_lines=True, show_header=False, title=f'[bold]{device_name} :: {today}')
        main_table.add_column(justify="right", style="magenta")
        main_table.add_column(justify="right", style="green")
        main_table.add_column(justify="right", style="magenta")
        main_table.add_row(sys_info_table, protocols_table, mem_cpu_commit_table)

        self.query_one('#load1').display = False
        self.query_one("#static1_1", Static).update(main_table)

    def on_auto_complete_selected(self, event) -> None:
        """Run when user hits tab or enter after selecting the input from the dropdown"""
        user_input = self.query_one("#card_name")
        if user_input.value:
            # Get user input when user hits tab
            self.card_fetch(user_input.value)

    @work
    def card_fetch(self, card_name):
        self.query_one('#load2').display = True
        card_search_output = nr.run(task=pyez_rpc, func='get-chassis-inventory')
        router_list = list(dict.keys(card_search_output))
        self.query_one('#load2').display = False
        final_card_result = ''
        for router in router_list:
            card_result = card_search_output[router][0].result
            module_list = card_result['chassis-inventory']['chassis']['chassis-module']
            for module in module_list:
                if 'FPC' in module['name'] and card_name == module['model-number']:
                    final_card_result = f": {router} : {module['name']} > {module['model-number']}" + \
                                        '\n' + final_card_result

        if final_card_result != '':
            self.query_one("#out", Static).update(Syntax(final_card_result, "teratermmacro",
                                                         theme="vs", line_numbers=True))
        else:
            self.query_one("#out", Static).update(Syntax('Card Not Found!', "teratermmacro",
                                                         theme="vs", line_numbers=True))

    @work
    def cfg_fetch(self, cfg_search):
        self.query_one('#load2').display = True
        cfg_search_output = nr.run(task=napalm_cli, commands=[f'show configuration | display set | match {cfg_search}'])
        router_list = list(dict.keys(cfg_search_output))
        cfg_search_result = ''
        self.query_one('#load2').display = False
        for router in router_list:
            cfg_result = cfg_search_output[router][0].result
            for key, value in cfg_result.items():
                if value != "":
                    cfg_search_result = cfg_search_result + f'~~ Config found in {router} ~~\n{value}\n\n'

        self.query_one("#out", Static).update(Syntax(cfg_search_result, "teratermmacro",
                                                     theme="vs", line_numbers=True))

    @work
    def cmd_fetch(self, cmds):
        self.query_one('#load2').display = True
        cmds_list = cmds.split(',')
        cmd_fetch_output = nr.run(task=napalm_cli, commands=cmds_list)
        router_list = list(dict.keys(cmd_fetch_output))
        self.query_one('#load2').display = False
        cmd_fetch_result = ''
        for router in router_list:
            cmd_result = cmd_fetch_output[router][0].result
            cmd_str = re.sub(" ", "_", cmds)
            final_out = cmd_result[cmds]
            cmd_fetch_result = cmd_fetch_result + f"^^^ {today}/{cmd_str}/{router} ^^^^\n\n{final_out.strip()}\n\n\n"
        self.query_one("#out", Static).update(Syntax(cmd_fetch_result, "teratermmacro",
                                                     theme="vs", line_numbers=True))

    @work
    def checks_generate(self, device_name, level):
        self.query_one("#gen_out", Static).update('')
        self.query_one('#load3').display = True
        new_nr = nr.filter(site=device_name)
        unique_protocols = protocol_list(new_nr, device_name)

        # Loading cmds.yaml
        with open("cmds.yml", "r") as f:
            try:
                all_cmds = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                print(exc)

        cmds_list = []
        protocols_na = ''
        for protocol in unique_protocols:
            try:
                cmds_list.append(all_cmds[protocol][level])
            except KeyError:
                protocols_na += protocol + '\n'
        self.query_one('#load3').display = False
        self.query_one("#gen_out", Static).update(Syntax
                                                  (f'Checks are not available for following protocols\n{protocols_na}',
                                                   "teratermmacro", theme="vs", line_numbers=True))
        global final_cmds
        final_cmds = ''
        for cmds in cmds_list:
            for c in cmds:
                final_cmds += c + '\n'

        self.query_one("#gen_out", Static).update(Syntax(final_cmds, "teratermmacro",
                                                         theme="vs", line_numbers=True))

    @work
    def action_fetch_output(self):
        if self.query_one(TabbedContent).active == "gen":
            self.query_one("#gen_out", Static).update('')
            device_name = self.query_one("#device_name2").value
            self.query_one('#load3').display = True
            new_nr = nr.filter(site=device_name)
            commands = final_cmds.splitlines()
            fetch_result = new_nr.run(task=napalm_cli, commands=commands)
            fetch_output = fetch_result[device_name][0].result
            self.query_one('#load3').display = False
            for key, value in fetch_output.items():
                with open(f"{device_name}_{today}_cmd_output.txt", 'a') as f:
                    f.write(f"**** {key} ***\n{value}")

            self.query_one("#gen_out", Static).update(
                Syntax(
                    f'Output from {device_name} saved to {device_name}_{today}_cmd_output.txt',
                    "teratermmacro", theme="vs", line_numbers=False))
        else:
            pass

    def action_copy_cmds(self):
        pyperclip.copy(final_cmds)
        if self.query_one(TabbedContent).active == "gen":
            # self.query_one("#gen_out", Static).update('commands copied to clipboard!')
            self.notify('commands copied to clipboard!')
        else:
            pass

    def action_save_snap(self):
        if self.query_one(TabbedContent).active == "dash":
            console.save_svg("dash.svg", title="dash_snap")
            self.query_one("#static1_1", Static).update("Dashboard snapshot saved")
        else:
            pass


if __name__ == "__main__":
    app = NetTUI()
    app.run()
