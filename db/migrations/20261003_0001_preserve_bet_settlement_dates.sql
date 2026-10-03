-- Editing a settled bet must not move its profit into the current week.
-- Keep existing profit calculations and accept explicit historical dates.
CREATE OR REPLACE FUNCTION public.calculate_profit_loss()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $function$
BEGIN
  IF NEW.status = 'won' THEN
    NEW.profit_loss = ROUND((NEW.odds - 1) * NEW.stake, 2);
  ELSIF NEW.status = 'lost' THEN
    NEW.profit_loss = -NEW.stake;
  ELSIF NEW.status = 'void' THEN
    NEW.profit_loss = 0;
  ELSIF NEW.status = 'pending' THEN
    NEW.profit_loss = NULL;
    NEW.settled_at = NULL;
  END IF;

  IF NEW.status IN ('won', 'lost', 'void') THEN
    IF TG_OP = 'UPDATE' THEN
      IF OLD.status IN ('won', 'lost', 'void') THEN
        NEW.settled_at = COALESCE(NEW.settled_at, OLD.settled_at, NOW());
      ELSE
        NEW.settled_at = COALESCE(NEW.settled_at, NOW());
      END IF;
    ELSE
      NEW.settled_at = COALESCE(NEW.settled_at, NOW());
    END IF;
  END IF;
  RETURN NEW;
END;
$function$;
