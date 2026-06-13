"""Build role-permission-matrix.canvas.tsx from ROLE_PERMISSION_MATRIX_COMPACT.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPACT = ROOT / 'ROLE_PERMISSION_MATRIX_COMPACT.json'
CANVAS = Path(r'C:\Users\Surex\.cursor\projects\e-Infomates-Development-infomates-oms\canvases\role-permission-matrix.canvas.tsx')

data = json.loads(COMPACT.read_text(encoding='utf-8'))
short = {
    'Admin / Super User': 'Admin',
    'Operations Manager': 'Ops Mgr',
    'Project Manager': 'PM',
    'Project Supervisor': 'Supervisor',
    'Field Engineer': 'Engineer',
    'Field Technician': 'Technician',
    'Accounts Manager': 'Accounts',
    'Accounts Executive': 'Acct Exec',
    'Back Office Staff': 'Back Office',
}
payload = {
    'roles': data['roles'],
    'rolesShort': [short.get(r, r) for r in data['roles']],
    'rows': data['menus'] + data['permissions'],
    'dashboards': data['dashboards'],
}

CANVAS.write_text(f'''import {{ useMemo, useState }} from "cursor/canvas";
import {{
  Card, CardBody, CardHeader, H1, Text, Stack, Row, Select, TextInput,
  Table, Pill, Stat, Grid, useHostTheme,
}} from "cursor/canvas";

const DATA = {json.dumps(payload)} as const;

type Row = {{ module: string; action: string }} & Record<string, boolean | string>;

function allowed(role: string, row: Row) {{
  return row[role] === true;
}}

export default function RolePermissionMatrix() {{
  const theme = useHostTheme();
  const [roleFilter, setRoleFilter] = useState("All Roles");
  const [moduleFilter, setModuleFilter] = useState("All Modules");
  const [search, setSearch] = useState("");

  const modules = useMemo(() => {{
    const s = new Set<string>();
    DATA.rows.forEach((r) => s.add(r.module));
    return ["All Modules", ...Array.from(s).sort()];
  }}, []);

  const filtered = useMemo(() => {{
    return DATA.rows.filter((r) => {{
      if (moduleFilter !== "All Modules" && r.module !== moduleFilter) return false;
      if (search) {{
        const q = search.toLowerCase();
        if (!r.module.toLowerCase().includes(q) && !r.action.toLowerCase().includes(q)) return false;
      }}
      if (roleFilter !== "All Roles") return allowed(roleFilter, r as Row);
      return true;
    }});
  }}, [moduleFilter, search, roleFilter]);

  const tableColumns = useMemo(() => {{
    if (roleFilter !== "All Roles") {{
      return [
        {{ key: "module", label: "Module", width: "28%" }},
        {{ key: "action", label: "Action", width: "22%" }},
        {{ key: "allowed", label: roleFilter, width: "12%", align: "center" as const }},
      ];
    }}
    return [
      {{ key: "module", label: "Module", width: "16%" }},
      {{ key: "action", label: "Action", width: "12%" }},
      ...DATA.rolesShort.map((s, i) => ({{ key: DATA.roles[i], label: s, width: "7%", align: "center" as const }})),
    ];
  }}, [roleFilter]);

  const tableRows = filtered.map((r, i) => {{
    if (roleFilter !== "All Roles") {{
      const ok = allowed(roleFilter, r as Row);
      return {{ key: String(i), cells: [r.module, r.action, ok ? "Yes" : "No"], tone: ok ? "success" : "neutral" }};
    }}
    return {{
      key: String(i),
      cells: [r.module, r.action, ...DATA.roles.map((role) => (allowed(role, r as Row) ? "Yes" : "—"))],
    }};
  }});

  return (
    <Stack gap={{20}} style={{{{ padding: 24, fontFamily: theme.font.sans }}}}>
      <Stack gap={{6}}>
        <H1>IOMS Role-Permission Matrix</H1>
        <Text tone="muted">Version 1.4.1 · 10 roles · 15 menus · 71 permission actions</Text>
      </Stack>

      <Grid columns={{5}} gap={{12}}>
        {{DATA.roles.map((role) => (
          <Stat
            key={{role}}
            label={{role}}
            value={{String(DATA.rows.filter((r) => allowed(role, r as Row)).length)}}
          />
        ))}}
      </Grid>

      <Card>
        <CardHeader title="Default Dashboards" />
        <CardBody>
          <Table
            columns={{[
              {{ key: "role", label: "Role", width: "40%" }},
              {{ key: "dash", label: "Dashboard URL", width: "60%" }},
            ]}}
            rows={{DATA.roles.map((r, i) => ({{ key: String(i), cells: [r, DATA.dashboards[r] || "—"] }}))}}
          />
        </CardBody>
      </Card>

      <Row gap={{12}} wrap>
        <Select label="Filter by role" value={{roleFilter}} onChange={{setRoleFilter}} options={{["All Roles", ...DATA.roles]}} />
        <Select label="Filter by module" value={{moduleFilter}} onChange={{setModuleFilter}} options={{modules}} />
        <TextInput label="Search" value={{search}} onChange={{setSearch}} placeholder="Module or action…" />
      </Row>

      {{roleFilter !== "All Roles" && (
        <Pill tone="info">{{filtered.length}} rows for {{roleFilter}}</Pill>
      )}}

      <Card>
        <CardHeader title="Permission Matrix" subtitle="{{filtered.length}} rows" />
        <CardBody style={{{{ padding: 0 }}}}>
          <Table columns={{tableColumns}} rows={{tableRows}} stickyHeader />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Notes" />
        <CardBody>
          <Text>Yes = permitted · — = denied · Superuser bypasses all module checks at runtime.</Text>
          <Text tone="muted">Delete actions are not exposed in IOMS UI. User CRUD is Django Admin (Superuser only).</Text>
          <Text tone="muted">Regenerate JSON: python manage.py role_permission_report</Text>
        </CardBody>
      </Card>
    </Stack>
  );
}}
''', encoding='utf-8')
print(f'Wrote {CANVAS}')
