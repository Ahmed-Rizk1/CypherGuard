import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Assuming we can import the consumer_loop from one of the services to test the graceful shutdown logic
from extractor.main import consumer_loop as extractor_consumer, _shutdown_event as ext_shutdown
from ml_engine.main import consumer_loop as ml_consumer, _shutdown_event as ml_shutdown
from firewall.main import consumer_loop as fw_consumer, _shutdown_event as fw_shutdown

@pytest.mark.asyncio
async def test_extractor_graceful_shutdown():
    """Ensure the extractor consumer loop exits when the shutdown event is set."""
    ext_shutdown.set()
    
    # Run the consumer loop. It should exit immediately without blocking.
    try:
        await asyncio.wait_for(extractor_consumer(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("Extractor consumer loop did not exit cleanly on shutdown signal")
    finally:
        ext_shutdown.clear()

@pytest.mark.asyncio
async def test_ml_engine_graceful_shutdown():
    """Ensure the ML engine consumer loop exits when the shutdown event is set."""
    ml_shutdown.set()
    
    try:
        await asyncio.wait_for(ml_consumer(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("ML engine consumer loop did not exit cleanly on shutdown signal")
    finally:
        ml_shutdown.clear()

@pytest.mark.asyncio
async def test_firewall_graceful_shutdown():
    """Ensure the firewall consumer loop exits when the shutdown event is set."""
    fw_shutdown.set()
    
    try:
        await asyncio.wait_for(fw_consumer(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("Firewall consumer loop did not exit cleanly on shutdown signal")
    finally:
        fw_shutdown.clear()
