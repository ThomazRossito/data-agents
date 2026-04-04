import sys
from rich.console import Console
from rich.panel import Panel

console = Console()

def run_fabric_health_check():
    """Valida token e conectividade base da CLI ou Azure Identity via M365/Entra."""
    console.print("\n[bold cyan]=== M365/Microsoft Fabric Health Check ===[/bold cyan]\n")
    
    try:
        from azure.identity import DefaultAzureCredential
        from azure.core.exceptions import ClientAuthenticationError
    except ImportError:
        console.print("[dim]Instalando utilitários... (execute `pip install azure-identity`)[/dim]")
        sys.exit(1)

    try:
        # DefaultAzureCredential tentará encontrar credenciais do az cli, env vars ou service principal
        console.print("[dim]1. Inferindo Credenciais do Sistema (Entra ID)...[/dim]")
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        
        # O scope da API do Fabric
        fabric_scope = "https://api.fabric.microsoft.com/.default"
        
        console.print(f"[dim]2. Solicitando Token de Acesso para {fabric_scope}...[/dim]")
        
        # Testa se a credencial local ou Service Principal consegue assinar tokens pro Fabric
        token = credential.get_token(fabric_scope)
        
        if token:
            console.print(f"✅ Token do Microsoft Fabric gerado com Sucesso!")
            console.print(f"[dim]⚡ Validade (Epoch): {token.expires_on}[/dim]")
            console.print("\n[bold green]Tudo pronto![/bold green] O sistema MCP do Fabric possui tokens válidos no host atual.\n")

    except ClientAuthenticationError as e:
        console.print("\n[bold red]❌ Falha ao Autenticar no Microsoft Fabric/Azure:[/bold red]")
        console.print(str(e))
        console.print("\n[yellow]Ação Recomendada:[/yellow] Execute [bold]az login[/bold] no seu terminal se estiver rodando localmente, ou defina as VARIÁVEIS DE AMBIENTE de [bold]Service Principal (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)[/bold] caso esteja em Pipeline.")
    except Exception as e:
        console.print("\n[bold red]❌ Erro Inesperado:[/bold red]")
        console.print(str(e))

if __name__ == "__main__":
    run_fabric_health_check()
