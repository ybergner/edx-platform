# pylint: disable=attribute-defined-outside-init
"""
A mixin class for LTI 2.0 functionality.  This is really just done to refactor the code to
keep the LTIModule class from getting too big
"""
import json
import re
import mock
import urllib
import hashlib
import base64
import logging

from webob import Response
from xblock.core import XBlock
from oauthlib.oauth1 import Client

import xmodule.lti_module

log = logging.getLogger(__name__)

LTI_2_0_REST_SUFFIX_PARSER = re.compile(r"^user/(?P<anon_id>\w+)", re.UNICODE)
LTI_2_0_JSON_CONTENT_TYPE = 'application/vnd.ims.lis.v2.result+json'


class LTIError(Exception):
    """Error class for LTIModule and LTI20ModuleMixin"""
    pass


class LTI20ModuleMixin(object):
    """This class MUST be mixed into LTIModule.  It does not do anything on its own"""

    #  LTI 2.0 Result Service Support -- but for now only for PUTting the grade back into an LTI xmodule
    @XBlock.handler
    def lti_2_0_result_rest_handler(self, request, suffix):
        """
        This will in the future be the handler for the LTI 2.0 Result service REST endpoints.  Right now
        I'm (@jbau) just implementing the PUT interface first.  All other methods get 404'ed.  It really should
        be a 405, but LTI does not specify that as an acceptable return code.  See
        http://www.imsglobal.org/lti/ltiv2p0/uml/purl.imsglobal.org/vocab/lis/v2/outcomes/Result/service.html

        An example JSON object:
        {
         "@context" : "http://purl.imsglobal.org/ctx/lis/v2/Result",
         "@type" : "Result",
         "resultScore" : 0.83,
         "comment" : "This is exceptional work."
        }
        For PUTs, the content type must be "application/vnd.ims.lis.v2.result+json".
        Note the "@id" key is optional on PUT and we don't do anything with it.  Instead, we use the "suffix"
        parameter to parse out the user from the end of the URL.  An example endpoint url is
        http://localhost:8000/courses/org/num/run/xblock/i4x:;_;_org;_num;_lti;_GUID/handler_noauth/lti_2_0_result_rest_handler/user/<anon_id>
        so suffix is of the form "user/<anon_id>"
        Failures result in 401, 404, or 500s without any body.  Successes result in 200.  Again see
        http://www.imsglobal.org/lti/ltiv2p0/uml/purl.imsglobal.org/vocab/lis/v2/outcomes/Result/service.html
        (Note: this prevents good debug messages for the client.  So I'd advocate the creating
        another endpoint that doesn't conform to spec, but is nicer)
        """

        if self.system.debug:
            self._log_correct_authorization_header(request)

        try:
            anon_id = self.parse_lti_2_0_handler_suffix(suffix)
        except LTIError:
            return Response(status=404)  # 404 because a part of the URL (denoting the anon user id) is invalid
        try:
            self.verify_lti_2_0_result_rest_headers(request, verify_content_type=True)
        except LTIError:
            return Response(status=401)  # Unauthorized in this case.  401 is right

        real_user = self.system.get_real_user(anon_id)
        if not real_user:  # that means we can't save to database, as we do not have real user id.
            msg = "[LTI]: Real user not found against anon_id: {}".format(anon_id)
            log.debug(msg)
            return Response(status=404)  # have to do 404 due to spec, but 400 is better, with error msg in body
        if request.method == "PUT":
            return self._lti_2_0_result_put_handler(request, real_user)
        elif request.method == "GET":
            return self._lti_2_0_result_get_handler(request, real_user)
        elif request.method == "DELETE":
            return self._lti_2_0_result_del_handler(request, real_user)
        else:
            return Response(status=404)  # have to do 404 due to spec, but 405 is better, with error msg in body

    def _log_correct_authorization_header(self, request):
        """
        Helper function, used only in debug situations, that logs the correct Authorization header based on
        the request header and body according to OAuth 1 Body signing
        """
        sha1 = hashlib.sha1()
        sha1.update(request.body)
        oauth_body_hash = unicode(base64.b64encode(sha1.digest()))  # pylint: disable=too-many-function-args
        log.debug("[LTI] oauth_body_hash = {}".format(oauth_body_hash))
        client_key, client_secret = self.get_client_key_secret()
        client = Client(client_key, client_secret)
        params = client.get_oauth_params()
        params.append((u'oauth_body_hash', oauth_body_hash))
        mock_request = mock.Mock(
            uri=unicode(urllib.unquote(request.url)),
            headers=request.headers,
            body=u"",
            decoded_body=u"",
            oauth_params=params,
            http_method=unicode(request.method),
        )
        sig = client.get_oauth_signature(mock_request)
        mock_request.oauth_params.append((u'oauth_signature', sig))

        _, headers, _ = client._render(mock_request)  # pylint: disable=protected-access
        log.debug("\n\n#### COPY AND PASTE AUTHORIZATION HEADER ####\n{}\n####################################\n\n"
                  .format(headers['Authorization']))

    def parse_lti_2_0_handler_suffix(self, suffix):
        """
        parses the suffix argument (the trailing parts of the URL) of the LTI2.0 REST handler.
        must be of the form "user/<anon_id>".  Returns anon_id if match found, otherwise raises LTIError
        """
        if suffix:
            match_obj = LTI_2_0_REST_SUFFIX_PARSER.match(suffix)
            if match_obj:
                return match_obj.group('anon_id')
        # fall-through handles all error cases
        msg = "No valid user id found in endpoint URL"
        log.debug("[LTI]: {}".format(msg))
        raise LTIError(msg)

    def _lti_2_0_result_get_handler(self, request, real_user):  # pylint: disable=unused-argument
        """
        GET handler for lti_2_0_result.  Assumes all authorization has been checked.
        """
        base_json_obj = {"@context": "http://purl.imsglobal.org/ctx/lis/v2/Result",
                         "@type": "Result"}
        self.system.rebind_noauth_module_to_user(self, real_user)
        if self.module_score is None:  # In this case, no score has been ever set
            return Response(json.dumps(base_json_obj), content_type=LTI_2_0_JSON_CONTENT_TYPE)

        # Fall through to returning grade and comment
        base_json_obj['resultScore'] = round(self.module_score, 2)
        base_json_obj['comment'] = self.score_comment
        return Response(json.dumps(base_json_obj), content_type=LTI_2_0_JSON_CONTENT_TYPE)

    def _lti_2_0_result_del_handler(self, request, real_user):  # pylint: disable=unused-argument
        """
        DELETE handler for lti_2_0_result.  Assumes all authorization has been checked.
        """
        self.clear_user_module_score(real_user)
        return Response(status=200)

    def _lti_2_0_result_put_handler(self, request, real_user):
        """
        PUT handler for lti_2_0_result.  Assumes all authorization has been checked.
        """
        try:
            (score, comment) = self.parse_lti_2_0_result_json(request.body)
        except LTIError:
            return Response(status=404)  # have to do 404 due to spec, but 400 is better, with error msg in body

        # According to http://www.imsglobal.org/lti/ltiv2p0/ltiIMGv2p0.html#_Toc361225514
        # PUTting a JSON object with no "resultScore" field is equivalent to a DELETE.
        if score is None:
            self.clear_user_module_score(real_user)
            return Response(status=200)

        # Fall-through record the score and the comment in the module
        self.set_user_module_score(real_user, score, self.max_score(), comment)
        return Response(status=200)

    def clear_user_module_score(self, user):
        """
        Clears the module user state, including grades and comments.
        Note that the publish call has to complete before we rebind and set this module state.
        The reason is because rebinding "caches" the state, so publishing between rebinding and setting
        state can cause state inconsistency
        """
        self.system.publish(
            self,
            'grade',
            {
                'value': None,
                'max_value': None,
                'user_id': user.id
            },
        )

        self.system.rebind_noauth_module_to_user(self, user)
        self.module_score = xmodule.lti_module.LTIModule.module_score.default
        self.score_comment = xmodule.lti_module.LTIModule.score_comment.default

    def set_user_module_score(self, user, score, max_score, comment=""):
        """
        Sets the module user state, including grades and comments.
        Note that the publish call has to complete before we rebind and set this module state.
        The reason is because rebinding "caches" the state, so publishing between rebinding and setting
        state can cause state inconsistency
        """
        scaled_score = score * max_score

        # have to publish for the progress page...
        self.system.publish(
            self,
            'grade',
            {
                'value': scaled_score,
                'max_value': max_score,
                'user_id': user.id,
            },
        )
        self.system.rebind_noauth_module_to_user(self, user)

        self.module_score = scaled_score
        self.score_comment = comment

    def verify_lti_2_0_result_rest_headers(self, request, verify_content_type=True):
        """
        Helper method to validate LTI 2.0 REST result service HTTP headers.  returns if correct, else raises LTIError
        """
        content_type = request.headers.get('Content-Type')
        if verify_content_type and content_type != LTI_2_0_JSON_CONTENT_TYPE:
            log.debug("[LTI]: v2.0 result service -- bad Content-Type: {}".format(content_type))
            raise LTIError(
                "For LTI 2.0 result service, Content-Type must be {}.  Got {}".format(LTI_2_0_JSON_CONTENT_TYPE,
                                                                                      content_type))
        try:
            self.verify_oauth_body_sign(request, content_type=LTI_2_0_JSON_CONTENT_TYPE)
        except (ValueError, LTIError) as err:
            log.debug("[LTI]: v2.0 result service -- OAuth body verification failed:  {}".format(err.message))
            raise LTIError(err.message)

    def parse_lti_2_0_result_json(self, json_str):
        """
        Helper method for verifying LTI 2.0 JSON object.
        The json_str must be loadable.  It can either be an dict (object) or an array whose first element is an dict,
        in which case that first dict is considered.
        The dict must have the "@type" key with value equal to "Result",
        "resultScore" key with value equal to a number [0, 1],
        The "@context" key must be present, but we don't do anything with it.  And the "comment" key may be
        present, in which case it must be a string.

        Returns (score, [optional]comment) if all checks out
        """
        try:
            json_obj = json.loads(json_str)
        except (ValueError, TypeError):
            msg = "Supplied JSON string in request body could not be decoded: {}".format(json_str)
            log.debug("[LTI] {}".format(msg))
            raise LTIError(msg)

        # the standard supports a list of objects, who knows why. It must contain at least 1 element, and the
        # first element must be a dict
        if type(json_obj) != dict:
            if type(json_obj) == list and len(json_obj) >= 1 and type(json_obj[0]) == dict:
                json_obj = json_obj[0]
            else:
                msg = ("Supplied JSON string is a list that does not contain an object as the first element. {}"
                       .format(json_str))
                log.debug("[LTI] {}".format(msg))
                raise LTIError(msg)

        # '@type' must be "Result"
        result_type = json_obj.get("@type")
        if result_type != "Result":
            msg = "JSON object does not contain correct @type attribute (should be 'Result', is {})".format(result_type)
            log.debug("[LTI] {}".format(msg))
            raise LTIError(msg)

        # '@context' must be present as a key
        REQUIRED_KEYS = ["@context"]  # pylint: disable=invalid-name
        for key in REQUIRED_KEYS:
            if key not in json_obj:
                msg = "JSON object does not contain required key {}".format(key)
                log.debug("[LTI] {}".format(msg))
                raise LTIError(msg)

        # 'resultScore' is not present.  If this was a PUT this means it's actually a DELETE according
        # to the LTI spec.  We will indicate this by returning None as score, "" as comment.
        # The actual delete will be handled by the caller
        if "resultScore" not in json_obj:
            return None, json_obj.get('comment', "")

        # if present, 'resultScore' must be a number between 0 and 1 inclusive
        try:
            score = float(json_obj.get('resultScore', "unconvertable"))  # Check if float is present and the right type
            if not 0 <= score <= 1:
                msg = 'score value outside the permitted range of 0-1.'
                log.debug("[LTI] {}".format(msg))
                raise LTIError(msg)
        except (TypeError, ValueError) as err:
            msg = "Could not convert resultScore to float: {}".format(err.message)
            log.debug("[LTI] {}".format(msg))
            raise LTIError(msg)

        return score, json_obj.get('comment', "")
