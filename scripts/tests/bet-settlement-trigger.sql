-- Run inside a transaction after applying the migration. Only temporary rows
-- are changed. No real bets or sequence values are created by these tests.
CREATE TEMP TABLE settlement_trigger_test (LIKE public.bets) ON COMMIT DROP;
CREATE TRIGGER test_settlement BEFORE INSERT OR UPDATE ON settlement_trigger_test
FOR EACH ROW EXECUTE FUNCTION public.calculate_profit_loss();
DO $test$
DECLARE
  seed public.bets%ROWTYPE;
  actual settlement_trigger_test%ROWTYPE;
  original_date timestamptz := '2000-01-01T12:00:00Z';
BEGIN
  SELECT * INTO STRICT seed FROM public.bets ORDER BY id LIMIT 1;
  seed.id := -1;
  seed.status := 'pending';
  seed.settled_at := NULL;
  seed.profit_loss := NULL;
  seed.odds := 2.5;
  seed.stake := 1;
  INSERT INTO settlement_trigger_test SELECT (seed).*;
  SELECT * INTO STRICT actual FROM settlement_trigger_test WHERE id = -1;
  IF actual.settled_at IS NOT NULL OR actual.profit_loss IS NOT NULL THEN RAISE EXCEPTION 'pending insert failed'; END IF;

  UPDATE settlement_trigger_test SET status = 'won' WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS DISTINCT FROM NOW() OR actual.profit_loss IS DISTINCT FROM 1.5 THEN RAISE EXCEPTION 'first settlement failed'; END IF;
  UPDATE settlement_trigger_test SET settled_at = original_date WHERE id = -1;
  UPDATE settlement_trigger_test SET event = 'Villarreal vs Sevilla' WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS DISTINCT FROM original_date OR actual.profit_loss IS DISTINCT FROM 1.5 THEN RAISE EXCEPTION 'name edit changed settlement'; END IF;
  UPDATE settlement_trigger_test SET settled_at = NULL WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS DISTINCT FROM original_date THEN RAISE EXCEPTION 'date fallback failed'; END IF;
  UPDATE settlement_trigger_test SET status = 'lost', stake = 2 WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS DISTINCT FROM original_date OR actual.profit_loss IS DISTINCT FROM -2 THEN RAISE EXCEPTION 'loss correction failed'; END IF;
  UPDATE settlement_trigger_test SET status = 'void' WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS DISTINCT FROM original_date OR actual.profit_loss IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'void correction failed'; END IF;
  UPDATE settlement_trigger_test SET status = 'pending' WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS NOT NULL OR actual.profit_loss IS NOT NULL THEN RAISE EXCEPTION 'reopen failed'; END IF;
  UPDATE settlement_trigger_test SET status = 'lost' WHERE id = -1 RETURNING * INTO actual;
  IF actual.settled_at IS DISTINCT FROM NOW() OR actual.profit_loss IS DISTINCT FROM -2 THEN RAISE EXCEPTION 'resettlement failed'; END IF;

  seed.id := -2;
  seed.status := 'won';
  seed.settled_at := original_date;
  INSERT INTO settlement_trigger_test SELECT (seed).*;
  SELECT * INTO STRICT actual FROM settlement_trigger_test WHERE id = -2;
  IF actual.settled_at IS DISTINCT FROM original_date OR actual.profit_loss IS DISTINCT FROM 1.5 THEN RAISE EXCEPTION 'historical insert failed'; END IF;
END;
$test$;
