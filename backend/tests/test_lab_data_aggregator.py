import base64
import io

import pandas as pd
import pytest
import respx
from httpx import Response

from lab_data_aggregator import gather_dataframes


def _encode(df: pd.DataFrame) -> str:
    buf = io.BytesIO()
    df.to_parquet(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.mark.asyncio
@respx.mock
async def test_gather_dataframes_prefixes_keys():
    pazuru_df = pd.DataFrame({"amount": [-42.0]})
    tsumi_df = pd.DataFrame({"symbol": ["BTC"]})

    respx.get("http://pazuru.local/api/lab/export").mock(
        return_value=Response(200, json={"transactions_df": _encode(pazuru_df)})
    )
    respx.get("http://tsumi.local/api/lab/export").mock(
        return_value=Response(200, json={"positions_df": _encode(tsumi_df)})
    )

    dfs = await gather_dataframes("http://pazuru.local", "http://tsumi.local", cookie="sess")

    assert set(dfs) == {"pazuru_transactions_df", "tsumi_positions_df"}
    assert dfs["pazuru_transactions_df"].iloc[0]["amount"] == -42.0


@pytest.mark.asyncio
@respx.mock
async def test_gather_dataframes_degrades_gracefully_on_failure():
    respx.get("http://pazuru.local/api/lab/export").mock(return_value=Response(500))
    respx.get("http://tsumi.local/api/lab/export").mock(return_value=Response(200, json={}))

    dfs = await gather_dataframes("http://pazuru.local", "http://tsumi.local", cookie=None)

    assert dfs == {}
