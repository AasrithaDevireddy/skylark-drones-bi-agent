from typing import Any, Dict, List, Optional
import requests

MONDAY_API_URL = "https://api.monday.com/v2"

class MondayAPIError(RuntimeError): pass

class MondayClient:
    """Read-only monday.com GraphQL client. Uses cursor pagination and never mutates boards."""
    def __init__(self, token: str, api_url: str = MONDAY_API_URL, timeout: int = 30):
        if not token: raise ValueError("Missing monday.com API token")
        self.token, self.api_url, self.timeout = token, api_url, timeout

    def _request(self, query: str, variables: Optional[Dict[str,Any]]=None):
        headers={"Authorization":self.token,"Content-Type":"application/json","API-Version":"2026-04"}
        try: r=requests.post(self.api_url,headers=headers,json={"query":query,"variables":variables or {}},timeout=self.timeout)
        except requests.RequestException as e: raise MondayAPIError(f"monday.com connection failed: {e}") from e
        if r.status_code != 200: raise MondayAPIError(f"monday.com returned HTTP {r.status_code}: {r.text[:500]}")
        try: payload=r.json()
        except ValueError as e: raise MondayAPIError("monday.com returned a non-JSON response") from e
        if payload.get("errors"):
            raise MondayAPIError("; ".join(str(x.get("message",x)) for x in payload["errors"]))
        return payload.get("data",{})

    def get_board_info(self, board_id: str):
        q="""query($ids:[ID!]){boards(ids:$ids){id name state columns{id title type}}}"""
        try: bid=int(str(board_id).strip())
        except ValueError as e: raise MondayAPIError(f"Invalid board ID: {board_id}") from e
        boards=self._request(q,{"ids":[bid]}).get("boards",[])
        if not boards: raise MondayAPIError(f"Board {board_id} was not found or is not accessible.")
        return boards[0]

    def get_all_items(self, board_id: str, page_size: int=500)->List[Dict[str,Any]]:
        q="""query($ids:[ID!],$limit:Int){boards(ids:$ids){items_page(limit:$limit){cursor items{id name url created_at updated_at column_values{id text value type}}}}}"""
        nq="""query($cursor:String!,$limit:Int){next_items_page(cursor:$cursor,limit:$limit){cursor items{id name url created_at updated_at column_values{id text value type}}}}"""
        try: bid=int(str(board_id).strip())
        except ValueError as e: raise MondayAPIError(f"Invalid board ID: {board_id}") from e
        boards=self._request(q,{"ids":[bid],"limit":min(page_size,500)}).get("boards",[])
        if not boards: raise MondayAPIError(f"Board {board_id} was not found or is not accessible.")
        page=boards[0].get("items_page",{}); items=list(page.get("items",[])); cursor=page.get("cursor")
        while cursor:
            page=self._request(nq,{"cursor":cursor,"limit":min(page_size,500)}).get("next_items_page",{})
            items.extend(page.get("items",[])); cursor=page.get("cursor")
        return items

    def read_board(self, board_id: str):
        return {"board":self.get_board_info(board_id),"items":self.get_all_items(board_id)}
