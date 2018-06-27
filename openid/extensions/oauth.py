#An Implementation of the OpenID OAuth Extension

from openid.extension import Extension

NS_URI = "http://specs.openid.net/extensions/oauth/1.0"
class OAuthRequest(Extension):
    # An OAuth token request, sent from a relying
    # party to a provider
    def __init__(self, ns_alias='oauth', consumer=None, scope=None):
        self.ns_alias = ns_alias
        self.ns_uri = NS_URI
        self.consumer = consumer
        self.scope = scope

    def getExtensionArgs(self):
        ns_args = {}
        ns_args['consumer'] = self.consumer
        ns_args['scope'] = self.scope
        return ns_args

    # Instantiate a Request object from the arguments in a
    # checkid_* OpenID message
    # return nil if the extension was not requested.

    @classmethod
    def fromOpenIDRequest(cls, openid_request):
        oauth_request = cls()
        args = openid_request.message.get_args(NS_URI)
        if args == {}:
          return None
        oauth_request.parseExtensionArgs(args)
        return oauth_request

    # Set the state of this request to be that expressed in these
    # OAuth arguments
    def parseExtensionArgs(args):
        self.consumer = args.get('consumer')
        self.scope = args.get('scope')

# A OAuth request token response, sent from a provider
# to a relying party
class OAuthResponse(Extension):
    def __init__(self, ns_alias='oauth', request_token=None, scope=None):
        self.ns_alias = ns_alias
        self.ns_uri = NS_URI
        self.request_token = request_token
        self.scope = scope

    # Create a Response object from an openid.consumer.consumer.SuccessResponse
    @classmethod
    def fromSuccessResponse(cls, success_response, signed=True):
        args = success_response.extensionResponse(NS_URI, signed)
        if args == None:
            return None
        oauth_response = cls()
        oauth_response.parseExtensionArgs(args)
        return oauth_response

    # parse the oauth request arguments into the
    # internal state of this object
    # if strict is specified, raise an exception when bad data is
    # encountered
    def parseExtensionArgs(self, args, strict=False):
        self.request_token = args.get('request_token')
        self.scope = args.get('scope')

    def getExtensionArgs(self):
        ns_args = {}
        ns_args['request_token'] = self.request_token
        ns_args['scope'] = self.scope
        return ns_args
