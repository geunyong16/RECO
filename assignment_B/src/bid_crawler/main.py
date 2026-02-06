"""
CLI 진입점

명령줄에서 크롤러를 실행하고 제어합니다.
"""

import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from bid_crawler.config import CrawlerConfig
from bid_crawler.crawler import BidCrawler, run_crawler
from bid_crawler.scheduler.cron import run_scheduled
from bid_crawler.storage.state_manager import StateManager
from bid_crawler.utils.logger import setup_logger

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="bid-crawler")
def cli():
    """
    누리장터 입찰공고 크롤러

    동적으로 렌더링되는 나라장터 입찰공고 페이지에서
    목록 및 상세 정보를 수집하여 저장합니다.
    """
    pass


@cli.command()
@click.option(
    "--max-pages", "-p",
    type=int,
    default=None,
    help="최대 크롤링 페이지 수"
)
@click.option(
    "--max-items", "-n",
    type=int,
    default=None,
    help="최대 수집 항목 수"
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default="data",
    help="출력 디렉토리"
)
@click.option(
    "--format", "-f",
    type=click.Choice(["json", "csv", "both"]),
    default="json",
    help="출력 형식"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="헤드리스 모드 (브라우저 창 숨김)"
)
@click.option(
    "--resume/--no-resume",
    default=True,
    help="이전 상태에서 재시작"
)
@click.option(
    "--keyword", "-k",
    type=str,
    default=None,
    help="검색 키워드"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="상세 로그 출력"
)
def crawl(
    max_pages: Optional[int],
    max_items: Optional[int],
    output_dir: str,
    format: str,
    headless: bool,
    resume: bool,
    keyword: Optional[str],
    verbose: bool,
):
    """
    입찰공고 크롤링 실행

    나라장터에서 입찰공고를 수집합니다.
    """
    # 설정 생성
    config = CrawlerConfig(
        max_pages=max_pages,
        max_items=max_items,
        keyword=keyword,
        log_level="DEBUG" if verbose else "INFO",
    )
    config.browser.headless = headless
    config.storage.data_dir = Path(output_dir)
    config.storage.output_format = format

    console.print(f"[bold blue]입찰공고 크롤러 v1.0.0[/bold blue]")
    console.print(f"출력 디렉토리: {output_dir}")
    console.print(f"출력 형식: {format}")
    if max_pages:
        console.print(f"최대 페이지: {max_pages}")
    if max_items:
        console.print(f"최대 항목: {max_items}")
    if keyword:
        console.print(f"검색 키워드: {keyword}")
    console.print()

    # 크롤링 실행
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("크롤링 중...", total=None)

        try:
            state = asyncio.run(run_crawler(config, resume=resume))

            progress.update(task, completed=True)

            # 결과 출력
            console.print()
            _print_summary(state.statistics)

        except KeyboardInterrupt:
            console.print("\n[yellow]사용자에 의해 중단됨[/yellow]")
        except Exception as e:
            console.print(f"\n[red]오류 발생: {e}[/red]")
            raise


@cli.command()
@click.option(
    "--mode", "-m",
    type=click.Choice(["interval", "cron"]),
    default="interval",
    help="스케줄 모드"
)
@click.option(
    "--interval", "-i",
    type=int,
    default=60,
    help="실행 간격 (분, interval 모드)"
)
@click.option(
    "--cron", "-c",
    type=str,
    default="0 */6 * * *",
    help="cron 표현식 (cron 모드)"
)
@click.option(
    "--no-immediate",
    is_flag=True,
    help="시작 시 즉시 실행하지 않음"
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default="data",
    help="출력 디렉토리"
)
def schedule(
    mode: str,
    interval: int,
    cron: str,
    no_immediate: bool,
    output_dir: str,
):
    """
    스케줄된 크롤링 실행

    지정된 주기로 자동으로 크롤링을 실행합니다.
    """
    config = CrawlerConfig()
    config.storage.data_dir = Path(output_dir)

    console.print(f"[bold blue]스케줄러 시작[/bold blue]")
    console.print(f"모드: {mode}")
    if mode == "interval":
        console.print(f"간격: {interval}분")
    else:
        console.print(f"cron: {cron}")
    console.print(f"출력 디렉토리: {output_dir}")
    console.print()
    console.print("[dim]Ctrl+C로 중지[/dim]")
    console.print()

    try:
        asyncio.run(run_scheduled(
            crawler_config=config,
            mode=mode,
            interval_minutes=interval,
            cron_expression=cron,
            run_immediately=not no_immediate,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]스케줄러 중지됨[/yellow]")


@cli.command()
@click.option(
    "--state-file", "-s",
    type=click.Path(),
    default="data/crawl_state.json",
    help="상태 파일 경로"
)
def status(state_file: str):
    """
    크롤링 상태 확인

    현재 저장된 크롤링 상태를 표시합니다.
    """
    state_manager = StateManager(Path(state_file))
    state = state_manager.load()

    if not state:
        console.print("[yellow]저장된 상태가 없습니다[/yellow]")
        return

    # 상태 테이블
    table = Table(title="크롤링 상태")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="white")

    table.add_row("실행 ID", state.run_id)
    table.add_row("시작 시간", str(state.started_at))
    table.add_row("마지막 업데이트", str(state.last_updated_at))
    table.add_row("실행 중", "예" if state.is_running else "아니오")
    table.add_row("완료됨", "예" if state.is_completed else "아니오")

    console.print(table)
    console.print()

    # 진행 상황
    progress_table = Table(title="진행 상황")
    progress_table.add_column("항목", style="cyan")
    progress_table.add_column("값", style="white")

    progress_table.add_row("현재 페이지", str(state.progress.current_page))
    progress_table.add_row("전체 페이지", str(state.progress.total_pages or "알 수 없음"))
    progress_table.add_row("마지막 완료 페이지", str(state.progress.last_completed_page))

    console.print(progress_table)
    console.print()

    # 통계
    _print_summary(state.statistics)


@cli.command()
@click.option(
    "--state-file", "-s",
    type=click.Path(),
    default="data/crawl_state.json",
    help="상태 파일 경로"
)
@click.confirmation_option(prompt="상태 파일을 삭제하시겠습니까?")
def reset(state_file: str):
    """
    크롤링 상태 초기화

    저장된 상태를 삭제하여 처음부터 다시 시작합니다.
    """
    state_manager = StateManager(Path(state_file))
    state_manager.cleanup()
    console.print("[green]상태가 초기화되었습니다[/green]")


def _print_summary(statistics):
    """통계 요약 출력"""
    table = Table(title="크롤링 통계")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="white")

    table.add_row("전체 수집", f"{statistics.total_collected}건")
    table.add_row("목록 수집", f"{statistics.list_collected}건")
    table.add_row("상세 수집", f"{statistics.detail_collected}건")
    table.add_row("오류", f"{statistics.errors}건")
    table.add_row("재시도", f"{statistics.retries}회")
    table.add_row("중복 스킵", f"{statistics.skipped_duplicates}건")
    table.add_row("성공률", f"{statistics.success_rate:.1f}%")

    console.print(table)


def main():
    """메인 진입점"""
    cli()


if __name__ == "__main__":
    main()
