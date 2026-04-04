import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from rich.console import Console
from rich.table import Table

console = Console()

def run_health_check():
    console.print("\n[bold cyan]=== Databricks Enterprise Health Check ===[/bold cyan]\n")
    
    try:
        # Inicializa o WorkspaceClient autodetectando o ambiente (.env ou OAuth)
        w = WorkspaceClient()
        
        # Teste 1: Autenticação
        console.print("[dim]1. Testando autenticação...[/dim]")
        me = w.current_user.me()
        console.print(f"✅ Autenticado como: [bold green]{me.user_name}[/bold green]")
        
        # Teste 2: Workspace Info
        console.print("\n[dim]2. Coletando informações do Workspace...[/dim]")
        # Como o host nem sempre é óbvio no retorno do SDK, pegamos das configs de inicialização.
        console.print(f"✅ Host configurado: [bold]{w.config.host}[/bold]")
        
        # Teste 3: SQL Warehouses disponíveis
        console.print("\n[dim]3. Verificando SQL Warehouses disponíveis (Serverless/Pro)...[/dim]")
        warehouses = list(w.data_sources.list())
        
        if not warehouses:
            console.print("⚠️ Nenhum SQL Warehouse encontrado neste workspace.")
        else:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Nome", style="dim")
            table.add_column("ID")
            table.add_column("Tamanho")

            for wh in warehouses[:5]:  # Mostrar apenas os primeiros 5
                # Algumas chaves dependem da versão/formato específico da API, mas podemos recuperar dados gerais
                # Neste caso, usamos atributos do objeto retornado.
                if hasattr(wh, "name") and hasattr(wh, "id") and hasattr(wh, "size"):
                    table.add_row(wh.name, wh.id, wh.size)
            
            console.print(table)
            if len(warehouses) > 5:
                console.print(f"... e mais {len(warehouses) - 5} Warehouses omitidos.")

        console.print("\n[bold green]Tudo pronto![/bold green] O Servidor MCP funcionará perfeitamente com essas credenciais.\n")

    except DatabricksError as e:
        console.print("\n[bold red]❌ Falha ao comunicar com Databricks:[/bold red]")
        console.print(f"Erro: {str(e)}")
        console.print("Por favor, verifique suas variáveis de ambiente: DATABRICKS_HOST e DATABRICKS_TOKEN.")
    except Exception as e:
        console.print("\n[bold red]❌ Erro Inesperado:[/bold red]")
        console.print(str(e))


if __name__ == "__main__":
    # Carrega variáveis do arquivo .env, se disponível, para execuções locais via terminal.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    run_health_check()
