import sys
import urllib.request
import urllib.error
from rich.console import Console
from rich.table import Table

console = Console()


def run_fabric_health_check():
    """
    Valida token Entra ID e conectividade real com a API do Microsoft Fabric.

    Testes realizados:
      1. Geração de token via DefaultAzureCredential
      2. GET /v1/workspaces — lista workspaces acessíveis (prova conectividade de rede)
    """
    console.print("\n[bold cyan]=== M365/Microsoft Fabric Health Check ===[/bold cyan]\n")

    try:
        from azure.identity import DefaultAzureCredential
        from azure.core.exceptions import ClientAuthenticationError
    except ImportError:
        console.print("[dim]Dependência ausente. Execute: pip install azure-identity[/dim]")
        sys.exit(1)

    try:
        # Passo 1 — Obter token Entra ID
        console.print("[dim]1. Inferindo credenciais do sistema (Entra ID)...[/dim]")
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        fabric_scope = "https://api.fabric.microsoft.com/.default"

        console.print(f"[dim]2. Solicitando token para {fabric_scope}...[/dim]")
        token = credential.get_token(fabric_scope)
        console.print(f"✅ Token gerado com sucesso. [dim]Expira em (epoch): {token.expires_on}[/dim]")

        # Passo 2 — Testar conectividade real: listar workspaces via API REST do Fabric
        console.print("\n[dim]3. Testando conectividade com a API do Fabric (GET /v1/workspaces)...[/dim]")
        import json

        api_url = "https://api.fabric.microsoft.com/v1/workspaces"
        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())

        workspaces = body.get("value", [])
        if workspaces:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Nome", style="dim")
            table.add_column("ID")
            table.add_column("Tipo")

            for ws in workspaces[:5]:
                table.add_row(
                    ws.get("displayName", "-"),
                    ws.get("id", "-"),
                    ws.get("type", "-"),
                )
            console.print(table)
            if len(workspaces) > 5:
                console.print(f"... e mais {len(workspaces) - 5} workspaces omitidos.")
        else:
            console.print("⚠️  Nenhum workspace encontrado para este principal de serviço.")

        console.print(
            "\n[bold green]Tudo pronto![/bold green] "
            "Credenciais e conectividade com o Microsoft Fabric validadas com sucesso.\n"
        )

    except ClientAuthenticationError as e:
        console.print("\n[bold red]❌ Falha ao autenticar no Microsoft Fabric/Azure:[/bold red]")
        console.print(str(e))
        console.print(
            "\n[yellow]Ação recomendada:[/yellow] Execute [bold]az login[/bold] localmente ou "
            "configure [bold]AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET[/bold] "
            "para Service Principal."
        )
    except urllib.error.HTTPError as e:
        console.print(f"\n[bold red]❌ Erro HTTP ao acessar a API do Fabric:[/bold red] {e.code} {e.reason}")
        console.print("[dim]Verifique se o Service Principal tem permissão no tenant do Fabric.[/dim]")
    except Exception as e:
        console.print("\n[bold red]❌ Erro inesperado:[/bold red]")
        console.print(str(e))

if __name__ == "__main__":
    run_fabric_health_check()
