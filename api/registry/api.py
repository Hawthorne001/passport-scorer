import logging
from datetime import datetime
from typing import List

# --- Deduplication Modules
from account.deduplication.lifo import lifo
from account.models import AccountAPIKey, Community
from asgiref.sync import async_to_sync
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI, status
from ninja_extra.exceptions import APIException
from ninja_schema import Schema
from reader.passport_reader import get_did, get_passport
from registry.models import Passport, Score, Stamp
from registry.utils import get_signer, validate_credential, verify_issuer

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()


class InvalidSignerException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Address does not match signature."


class InvalidPassportCreationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Error Creating Passport."


class InvalidScoreRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to get score for provided community."


class Unauthorized(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid API Key."


class SubmitPassportPayload(Schema):
    address: str
    signature: str
    community: str  # TODO: gerald: community_id ???, and make it int


class ScoreResponse(Schema):
    # passport_id: int
    address: str
    score: str  # The score should be represented as string as it will be a decimal number


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            raise Unauthorized()
        try:
            key = request.META["HTTP_AUTHORIZATION"].split()[1]
            api_key = AccountAPIKey.objects.get_from_key(key)

            user_account = api_key.account

            if user_account:
                return user_account
        except AccountAPIKey.DoesNotExist:
            raise Unauthorized()


@router.post("/submit-passport", auth=ApiKey())
def submit_passport(request, payload: SubmitPassportPayload) -> List[ScoreResponse]:
    # TODO: gerald - test that checksummed & non-checksummed addresses work
    if get_signer(payload.signature).lower() != payload.address.lower():
        raise InvalidSignerException()

    # Get DID from address
    did = get_did(payload.address)
    log.debug("/submit-passport, payload=%s", payload)

    # Passport contents read from ceramic
    passport = get_passport(did)

    if not verify_issuer(passport):
        raise InvalidSignerException()

    # Get community object
    user_community = get_object_or_404(
        Community, id=payload.community, account=request.auth
    )

    try:
        # Check if stamp(s) with hash already exist and remove it/them from the incoming passport
        passport_to_be_saved = lifo(passport)

        # Save passport to Passport database (related to community by community_id)
        db_passport, _ = Passport.objects.update_or_create(
            address=payload.address.lower(),
            community=user_community,
            defaults={
                "passport": passport_to_be_saved,
            },
        )

        for stamp in passport_to_be_saved["stamps"]:
            stamp_return_errors = async_to_sync(validate_credential)(
                did, stamp["credential"]
            )
            stamp_expiration_date = datetime.strptime(
                stamp["credential"]["expirationDate"], "%Y-%m-%dT%H:%M:%SZ"
            )
            # check that expiration date is not in the past
            stamp_is_expired = stamp_expiration_date < datetime.now()
            if len(stamp_return_errors) == 0 and stamp_is_expired == False:
                db_stamp = Stamp.objects.create(
                    hash=stamp["credential"]["credentialSubject"]["hash"],
                    provider=stamp["provider"],
                    credential=stamp["credential"],
                    passport=db_passport,
                )
                db_stamp.save()
            else:
                log.debug(
                    "Stamp not created. Stamp=%s\nReason: errors=%s stamp_is_expired=%s",
                    stamp,
                    stamp_return_errors,
                    stamp_is_expired,
                )

        scorer = user_community.get_scorer()
        scores = scorer.compute_score([db_passport.id])

        score, _ = Score.objects.update_or_create(
            passport_id=db_passport.id, defaults=dict(score=scores[0])
        )

        return [
            {
                # "passport_id": score.passport.id,
                "address": score.passport.address,
                "score": Score.objects.get(
                    pk=score.id
                ).score,  # Just reading out the value from DB to have it as decimal formatted
            }
            for s in scores
        ]
    except Exception as e:
        log.error(
            "Error when handling passport submission. payload=%s",
            payload,
            exc_info=True,
        )
        InvalidPassportCreationException()


@router.get("/score/{int:community_id}/{str:address}", auth=ApiKey())
def get_score(request, address: str, community_id: int) -> ScoreResponse:
    try:
        # TODO: validate that community belongs to the account holding the ApiKey
        lower_address = address.lower()
        community = Community.objects.get(id=community_id)
        passport = Passport.objects.get(address=lower_address, community=community)
        score = Score.objects.get(passport=passport)
        return {
            "address": score.passport.address,
            "score": score.score,
        }
    except Exception as e:

        log.error(
            "Error when getting passport score. address=%s, community_id=%s",
            address,
            community_id,
            exc_info=True,
        )
        raise InvalidScoreRequestException()