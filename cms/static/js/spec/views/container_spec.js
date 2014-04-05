define([ "jquery", "js/spec/create_sinon", "URI", "js/views/container", "js/models/xblock_info",
    "js/views/feedback_notification", "jquery.simulate",
    "xmodule", "coffee/src/main", "xblock/cms.runtime.v1"],
    function ($, create_sinon, URI, ContainerView, XBlockInfo, Notification) {

        describe("Container View", function () {

            describe("Supports reordering components", function () {

                var model, containerView, mockContainerHTML, respondWithMockXBlockFragment;

                var splitTestUrl = "/xblock/ccc.dd.ee/branch/draft/block/AB_Test";

                // TODO: why did these end up being published locators in the HTML? Should be draft.
                // Check functionality in app and update mock HTML appropriately.
                var groupAUrl = "/xblock/ccc.dd.ee/branch/published/block/group_a";
                var groupA = "ccc.dd.ee/branch/published/block/group_a";
                var groupAText = "ccc.dd.ee/branch/published/block/html_4658c0f4c400";
                var groupAVideo = "ccc.dd.ee/branch/published/block/group_a_video";

                var groupBUrl = "/xblock/ccc.dd.ee/branch/published/block/group_b";
                var groupB = "ccc.dd.ee/branch/published/block/group_b";
                var groupBText = "ccc.dd.ee/branch/published/block/html_b5c18016d991";
                var groupBProblem = "ccc.dd.ee/branch/published/block/Checkboxes";

                mockContainerHTML = readFixtures('mock/mock-container.underscore');

                respondWithMockXBlockFragment = function (requests, response) {
                    var requestIndex = requests.length - 1;
                    create_sinon.respondWithJson(requests, response, requestIndex);
                };

                beforeEach(function () {
                    model = new XBlockInfo({
                        id: 'testCourse/branch/draft/split_test/splitFFF',
                        display_name: 'Test AB Test',
                        category: 'split_test'
                    });

                    containerView = new ContainerView({
                        model: model,
                        view: 'container_preview'
                    });
                });

                afterEach(function () {
                    containerView.remove();
                });

                var init = function (caller) {
                    var requests = create_sinon.requests(caller);
                    containerView.render();

                    respondWithMockXBlockFragment(requests, {
                        html: mockContainerHTML,
                        "resources": []
                    });

                    $('body').append(containerView.$el);
                    return requests;
                };

                var dragHandle = function (index, dy) {
                    containerView.$el.find(".drag-handle:eq(" + index + ")").simulate("drag", {dy: dy});
                };

                var verifyRequest = function (requests, reorderCallIndex, expectedURL, expectedChildren) {
                    // 0th call is the response to the initial render call to get HTML.
                    var request = requests[reorderCallIndex + 1];
                    expect(request.url).toEqual(expectedURL);
                    var children = (JSON.parse(request.requestBody)).children;
                    expect(children.length).toEqual(expectedChildren.length);
                    for (var i = 0; i < children.length; i++) {
                        expect(children[i]).toEqual(expectedChildren[i]);
                    }
                };

                var verifyNumReorderCalls = function (requests, expectedCalls) {
                    // Number of calls will be 1 more than expected because of the initial render call to get HTML.
                    expect(requests.length).toEqual(expectedCalls + 1);
                };

                var respondToRequest = function (requests, reorderCallIndex, status) {
                    // Number of calls will be 1 more than expected because of the initial render call to get HTML.
                    requests[reorderCallIndex + 1].respond(status);
                };

                it('does nothing if item not moved far enough', function () {
                    var requests = init(this);
                    // Drag the first thing in Group A (text component) down very slightly, but not past second thing.
                    dragHandle(1, 5);
                    verifyNumReorderCalls(requests, 0);
                });


                it('can reorder within a group', function () {
                    var requests = init(this);
                    // Drag the first thing in Group A (text component) after the second thing (video).
                    dragHandle(1, 80);
                    respondToRequest(requests, 0, 200);
                    verifyNumReorderCalls(requests, 1);
                    verifyRequest(requests, 0, groupAUrl, [groupAVideo, groupAText]);
                });

                it('can drag from one group to another', function () {
                    var requests = init(this);
                    // Drag the first thing in Group A (text component) into the second group.
                    dragHandle(1, 200);
                    respondToRequest(requests, 0, 200);
                    respondToRequest(requests, 1, 200);
                    // Will get an event to move into Group B and an event to remove from Group A.
                    verifyNumReorderCalls(requests, 2);
                    verifyRequest(requests, 0, groupBUrl, [groupBText, groupAText, groupBProblem]);
                    verifyRequest(requests, 1, groupAUrl, [groupAVideo]);
                });

                it('does not remove from old group if addition to new group fails', function () {
                    var requests = init(this);
                    // Drag the first thing in Group A (text component) into the second group.
                    dragHandle(1, 200);
                    respondToRequest(requests, 0, 500);
                    // Send failure for addition to new group-- no removal event should be received.
                    verifyNumReorderCalls(requests, 1);
                    verifyRequest(requests, 0, groupBUrl, [groupBText, groupAText, groupBProblem]);
                });

                it('can swap group A and group B', function () {
                    var requests = init(this);
                    // Drag Group B before group A.
                    dragHandle(3, -200);
                    respondToRequest(requests, 0, 200);
                    verifyNumReorderCalls(requests, 1);
                    verifyRequest(requests, 0, splitTestUrl, [groupB, groupA]);
                });

                it('can nest one group inside another', function () {
                    var requests = init(this);
                    // Drag Group A into Group B.
                    dragHandle(0, 100);
                    respondToRequest(requests, 0, 200);
                    // For some reason we are not getting the removal event in the test. :(
    //                requests[2].respond(200);
                    // Will get an event to move into Group B and an event to remove from Group A.
    //                expect(requests.length).toEqual(3);
    //                verifyRequest(requests[1], groupBUrl, [groupA, groupBText, groupBProblem]);
                    verifyRequest(requests, 0, splitTestUrl, [groupB]);
                });

                it('can drag a component to the top level', function () {
                    var requests = init(this);
                    // Drag text item in Group A to the top level (in first position).
                    dragHandle(1, -20);
                    respondToRequest(requests, 0, 200);
                    respondToRequest(requests, 1, 200);
                    verifyNumReorderCalls(requests, 2);
                    verifyRequest(requests, 0, splitTestUrl, [groupAText, groupA, groupB]);
                    verifyRequest(requests, 1, groupAUrl, [groupAVideo]);
                });

                describe("Shows a saving message", function () {
                    var savingSpies;

                    beforeEach(function () {
                        savingSpies = spyOnConstructor(Notification, "Mini",
                            ["show", "hide"]);
                        savingSpies.show.andReturn(savingSpies);
                    });

                    it('hides saving message upon success', function () {
                        var requests = init(this);
                        // Drag text item in Group A to the top level (in first position).
                        dragHandle(1, -20);
                        expect(savingSpies.constructor).toHaveBeenCalled();
                        expect(savingSpies.show).toHaveBeenCalled();
                        expect(savingSpies.hide).not.toHaveBeenCalled();
                        var savingOptions = savingSpies.constructor.mostRecentCall.args[0];
                        expect(savingOptions.title).toMatch(/Saving/);

                        respondToRequest(requests, 0, 200);
                        expect(savingSpies.hide).not.toHaveBeenCalled();
                        respondToRequest(requests, 1, 200);

                        expect(savingSpies.hide).toHaveBeenCalled();
                        verifyNumReorderCalls(requests, 2);
                    });

                    it('does not hide saving message if failure', function () {
                        var requests = init(this);
                        // Drag text item in Group A to the top level (in first position).
                        dragHandle(1, -20);
                        expect(savingSpies.constructor).toHaveBeenCalled();
                        expect(savingSpies.show).toHaveBeenCalled();
                        expect(savingSpies.hide).not.toHaveBeenCalled();

                        respondToRequest(requests, 0, 500);

                        expect(savingSpies.hide).not.toHaveBeenCalled();
                        // Since the first reorder call failed, the removal will not be called.
                        verifyNumReorderCalls(requests, 1);
                    });
                });
            });
        });
    });